using Microsoft.Dafny;
using DafnyDriver.Commands;
using Microsoft.Boogie;
using System.Text.Json;
using Std.Wrappers;
using System.Diagnostics.Metrics;

namespace ReturnMethodLinesRandom
{
    class Program
    {
        static async Task<int> Main(string[] args)
        {
            if (args.Length == 0)
            {
                Console.WriteLine("Usage: program <file.dfy> [method] [postcondition]");
                return 1;
            }

            var config = new VerificationConfig
            {
                ProgramFile = args[0],
                MethodName = args.Length > 1 ? args[1] : "",
                PostCondition = args.Length > 2 ? args[2] : ""
            };

            var runner = new VerificationRunner(config);
            await runner.Run();

            return 0;
        }
    }

    class VerificationConfig
    {
        public string ProgramFile { get; init; }
        public string MethodName { get; init; }
        public string PostCondition { get; init; }
    }


    class VerificationRunner
    {
        private readonly VerificationConfig config;
        private int iteration = 0;

        public VerificationRunner(VerificationConfig config)
        {
            this.config = config;
        }

        public async Task Run()
        {
            string currentFile = config.ProgramFile;

            while (true)
            {
                var options = DafnyOptionsFactory.Create(currentFile);
                var compilation = CliCompilation.Create(options);
                compilation.Start();

                var resolution = await compilation.Resolution
                    ?? throw new InvalidOperationException("Resolution failed");

                var resolvedProgram = resolution.ResolvedProgram;

                // First: gather all failures
                var failedResults = new List<CanVerifyResult>();
                await foreach (var result in compilation.VerifyAllLazily())
                {
                    if (result.Results.Any(r => r.Result.Outcome == SolverOutcome.Invalid))
                        failedResults.Add(result);
                }

                if (failedResults.Count == 0)
                {
                    Console.WriteLine("Verification succeeded.");
                    break;
                }

                bool anyChange = false;

                // Process all failures sequentially
                foreach (var fail in failedResults)
                {
                    var handler = new VerificationFailureHandler(
                        config,
                        resolvedProgram,
                        iteration);

                    string? nextFile = await handler.Handle(fail, currentFile, options);

                    if (nextFile != null)
                    {
                        iteration++;
                        currentFile = nextFile;
                        anyChange = true;
                    }
                }

                if (!anyChange)
                {
                    Console.WriteLine("No changes possible from verification failures. Stopping.");
                    break;
                }
            }
        }
    }

    class VerificationFailureHandler
    {
        private readonly VerificationConfig config;
        private readonly Microsoft.Dafny.Program program;
        private readonly int iteration;

        public VerificationFailureHandler(
            VerificationConfig config,
            Microsoft.Dafny.Program program,
            int iteration)
        {
            this.config = config;
            this.program = program;
            this.iteration = iteration;
        }

        public async Task<string?> Handle(CanVerifyResult fail, string programFile, DafnyOptions options)
        {
            if (fail.CanVerify is not Method method || method.Body == null)
                return null;

            if (!string.IsNullOrEmpty(config.MethodName) &&
                method.Name != config.MethodName)
                return null;

            foreach (var taskResult in fail.Results)
            {
                foreach (var ce in taskResult.Result.CounterExamples)
                {
                    var analyzer = new CounterexampleAnalyzer();
                    var analysis = analyzer.Analyze(ce, method.Body, options);

                    if (!analysis.ShouldInject)
                        continue;

                    var mutator = new ProgramMutator();
                    return await mutator.InjectAssumeFalse(
                        program,
                        analysis,
                        programFile,
                        iteration,
                        config.PostCondition);
                }
            }

            return null;
        }
    }

    class CounterexampleAnalyzer
    {
        public AnalysisResult Analyze(Counterexample ce, BlockStmt body,  DafnyOptions options)
        {
            if (ce.Model == null)
                return AnalysisResult.Empty;

            var suspiciousNodes = new List<INode>();
            BlockStmt? firstBlockStmt = null;
            bool insideIf = false;

            var model = new DafnyModel(ce.Model, options);

            foreach (var state in model.States)
            {
                if (!state.StateContainsPosition()) continue;

                int line = state.GetLineId();
                int col = state.GetCharId();

                var visitor = new FindExpressionAndParentByTokenVisitor(line, col);
                visitor.VisitManual(body);

                if (!visitor.MatchingStatementWithAllParent.Any()) continue;

                var (stmt, parents) = visitor.MatchingStatementWithAllParent[0];

                while (parents.Count > 0)
                {
                    var parent = parents.Pop();

                    if (parent is BlockStmt block)
                        firstBlockStmt = block;

                    if (parent is IfStmt ifStmt)
                    {
                        insideIf = true;
                        if (!suspiciousNodes.Contains(ifStmt))
                            suspiciousNodes.Add(ifStmt);
                    }
                }

                suspiciousNodes.Add(stmt);
            }

            return new AnalysisResult(insideIf, firstBlockStmt, suspiciousNodes);
        }
    }

    class AnalysisResult
    {
        public bool ShouldInject => InsideIf && TargetBlock != null;

        public bool InsideIf { get; }
        public BlockStmt? TargetBlock { get; }
        public List<INode> SuspiciousNodes { get; }

        public static AnalysisResult Empty => new(false, null, new());

        public AnalysisResult(bool insideIf, BlockStmt? block, List<INode> nodes)
        {
            InsideIf = insideIf;
            TargetBlock = block;
            SuspiciousNodes = nodes;
        }
    }

    class ProgramMutator
    {
        public async Task<string> InjectAssumeFalse(
            Microsoft.Dafny.Program program,
            AnalysisResult analysis,
            string programFile,
            int iteration,
            string postcondition)
        {
            var block = analysis.TargetBlock!;
            var falseExpr = new Microsoft.Dafny.LiteralExpr(block.Origin, false);
            var assumeStmt = new AssumeStmt(block.Origin, falseExpr, block.Attributes);

            if (block.Body is not List<Statement> body)
                throw new InvalidOperationException("Block body not mutable");

            var newFile = programFile.Replace(".dfy", $"_{iteration}_iter.dfy");

            ProgramWriter.Write(program, newFile, analysis.SuspiciousNodes);

            body.Insert(0, assumeStmt);

            if (!string.IsNullOrEmpty(postcondition))
                Console.WriteLine($"// POSTCONDITION: {postcondition}");

            Console.WriteLine($"Injected assume false. Program modified -> {newFile}");

            var nextFile = programFile.Replace(".dfy", $"_{iteration + 1}_iter.dfy");

            ProgramWriter.Write(program, nextFile, new());

            return nextFile;
        }
    }

    static class ProgramWriter
    {
        public static void Write(Microsoft.Dafny.Program program, string path, List<INode> suspicious)
        {
            using var writer = new StreamWriter(path);
            var printer = new Printer(writer, program.Options, PrintModes.Everything, null);
            printer.PrintProgram(program, false);

            writer.WriteLine("// ---- Suspicious nodes ----");

            foreach (var node in suspicious)
                writer.WriteLine($"// line {node.StartToken.line}");
        }
    }

    class FindExpressionAndParentByTokenVisitor : ASTVisitor<IASTVisitorContext>
    {
        public readonly List<(Statement Stmt, Stack<INode> Parents)> MatchingStatementWithAllParent = new();
        private readonly int targetLine;
        private readonly int targetCol;
        private readonly Stack<INode> parents = new();

        public FindExpressionAndParentByTokenVisitor(int line, int col)
        {
            targetLine = line;
            targetCol = col;
        }

        public override IASTVisitorContext GetContext(IASTVisitorContext context, bool inFunctionPostcondition) => context;

        public void VisitManual(Statement stmt) => VisitStatement(stmt, null);

        protected override void VisitStatement(Statement stmt, IASTVisitorContext context)
        {
            if (IsTargetInStatement(stmt))
            {
                MatchingStatementWithAllParent.Add((stmt, new Stack<INode>(parents)));
            }

            parents.Push(stmt);
            base.VisitStatement(stmt, context);
            parents.Pop();
        }

        private bool IsTargetInStatement(Statement stmt)
        {
            bool lineMatch = stmt.StartToken.line <= targetLine && targetLine <= stmt.EndToken.line;
            bool colMatch = stmt.StartToken.col <= targetCol && targetCol <= stmt.EndToken.col;
            return lineMatch && colMatch;
        }
    }

    static class PathHelper
    {
        public static string FindRepoRoot(string marker = ".repo_verifixer_fault_localizaion_marker")
        {
            var current = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);

            while (current != null)
            {
                if (File.Exists(Path.Combine(current.FullName, marker)) ||
                    Directory.Exists(Path.Combine(current.FullName, marker)))
                {
                    return current.FullName;
                }
                current = current.Parent;
            }

            throw new DirectoryNotFoundException("Could not find repository root. Marker missing: " + marker);
        }
    }

    static class DafnyOptionsFactory
    {
        public static DafnyOptions Create(string filePath)
        {
            string repoRoot = PathHelper.FindRepoRoot();

            var options = new DafnyOptions(Console.In, Console.Out, Console.Error);
            options.ApplyDefaultOptions();

            options.Verify = true;
            options.DafnyVerify = true;
            options.EmitDebugInformation = true;
            options.Compile = false;
            options.DafnyPrelude = Path.Combine(repoRoot, "dafny", "Binaries", "DafnyPrelude.bpl");

            options.ModelViewFile = "-";
            options.ProverOptions.Add("O:model.completion=true");
            options.ProverOptions.Add("O:model.compact=false");
            options.Set(CommonOptionBag.AllowWarnings, true);
            options.Set(CommonOptionBag.ExtractCounterexample, true);

            options.CliRootSourceUris.Add(new Uri("file://" + Path.GetFullPath(filePath)));
            return options;
        }
    }
}