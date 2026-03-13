using Microsoft.Dafny;
using DafnyDriver.Commands;
using Microsoft.Boogie;
using System.Text.RegularExpressions;

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

            // --- Parse all solution files ---
            string tempDir = Path.Combine(Path.GetTempPath(), "DafnyFaultLocalization");
            if (!Directory.Exists(tempDir))
            {
                Console.WriteLine("No solution files found.");
                return 0;
            }

            var allSuspiciousLines = new List<List<int>>();
            var solutionFiles = Directory.GetFiles(tempDir, "*_solution.dfy");

            foreach (var file in solutionFiles)
            {
                var assumeFalseLines = new List<int>();
                var LooplineNumber = -1;

                var fileLinesShifter = new List<int>();
                var lines = await File.ReadAllLinesAsync(file);
                bool suspiciousSection = false;

                foreach (var line in lines)
                {
                    LooplineNumber += 1;
                    if(line.Contains("assume false"))
                    {
                        assumeFalseLines.Add(LooplineNumber);
                    }

                    if (line.Contains("---- Suspicious nodes ----"))
                    {
                        suspiciousSection = true;
                        continue;
                    }
                    if (suspiciousSection)
                    {
                        var match = Regex.Match(line, @"// line (\d+)");
                        if (match.Success && int.TryParse(match.Groups[1].Value, out int lineNumber))
                        {
                            // Need to find the original position ignoring the lines of assume false
                            // Basically if "assume false" line is before the line in question reduce the counter
                            foreach (var assumeFalseLine in assumeFalseLines)
                            {
                                if(assumeFalseLine < lineNumber)
                                {
                                    lineNumber -= 1;
                                }
                            }
                            fileLinesShifter.Add(lineNumber);
                        }
                        else if (line.StartsWith("// Postcondition"))
                        {
                            suspiciousSection = false;
                        }
                    }
                }
                allSuspiciousLines.Add(fileLinesShifter);
            }
            Console.WriteLine("[");
            foreach (var list in allSuspiciousLines)
            {
                Console.WriteLine("  [" + string.Join(", ", list) + "],");
            }
            Console.WriteLine("]");

            Directory.Delete(tempDir, true); 
            return 0;
        }
    }

    class StaticCounter
    {
        public static int GlobalIteration = 0;
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
        public VerificationRunner(VerificationConfig config)
        {
            this.config = config;
        }

        public async Task Run()
        {
            Queue<VerificationConfig> VerifConfToDo = new Queue<VerificationConfig>();
            VerifConfToDo.Enqueue(config);

            while (VerifConfToDo.Count > 0)
            {

                var currentConfig = VerifConfToDo.Dequeue();
                var currentFile = currentConfig.ProgramFile;

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
                    break;
                }

                // Process all failures sequentially
                foreach (var fail in failedResults)
                {
                    var handler = new VerificationFailureHandler(
                        config,
                        resolvedProgram);

                    List<VerificationConfig> nextFiles = await handler.Handle(fail, currentConfig, options);

                    foreach (var file in nextFiles)
                    {
                        VerifConfToDo.Enqueue(file);
                    }
                }
            }
        }
    }

    class VerificationFailureHandler
    {
        private readonly VerificationConfig config;
        private readonly Microsoft.Dafny.Program program;

        public VerificationFailureHandler(
            VerificationConfig config,
            Microsoft.Dafny.Program program)
        {
            this.config = config;
            this.program = program;
        }

        public async Task<List<VerificationConfig>> Handle(CanVerifyResult fail, VerificationConfig programConfig, DafnyOptions options)
        {
            List<VerificationConfig> next_files = new();

            if (fail.CanVerify is not Method method || method.Body == null)
                return next_files;

            if (!string.IsNullOrEmpty(config.MethodName) &&
                method.Name != config.MethodName)
                return next_files;

            foreach (var taskResult in fail.Results)
            {
                foreach (var ce in taskResult.Result.CounterExamples)
                {
                    var analyzer = new CounterexampleAnalyzer();
                    var analysis = analyzer.Analyze(ce, method.Body, options);

                    if (!analysis.ShouldInject)
                        continue;

                    var mutator = new ProgramMutator();

                    var postcondition = ce.FailingAssert.ToString();
                    var postconditionLine = ce.FailingAssert.Line;

                    if (programConfig.PostCondition != "" && programConfig.PostCondition != postcondition)
                    {
                        continue; // We only want to expand the same type of error (same failed postcondition)
                    }

                    next_files.Add(await mutator.InjectAssumeFalse(
                        program,
                        analysis,
                        postcondition,
                        postconditionLine));
                }
            }

            return next_files;
        }
    }

    class CounterexampleAnalyzer
    {
        public AnalysisResult Analyze(Counterexample ce, BlockStmt body, DafnyOptions options)
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
        private static readonly string TempWorkDir = Path.Combine(Path.GetTempPath(), "DafnyFaultLocalization");
        public async Task<VerificationConfig> InjectAssumeFalse(
            Microsoft.Dafny.Program program,
            AnalysisResult analysis,
            string postcondition,
            int postconditionLine)
        {
            if (!Directory.Exists(TempWorkDir))
            {
                Directory.CreateDirectory(TempWorkDir);
            }
            //Console.WriteLine($"[Storage] Working Directory: {TempWorkDir}");

            var block = analysis.TargetBlock!;
            // Origin relates source code with position of the token (in this case)
            // We will ignore it shortly afterwards so will just put the block.Origin
            var falseExpr = new Microsoft.Dafny.LiteralExpr(block.Origin, false);
            var assumeStmt = new AssumeStmt(block.Origin, falseExpr, null);

            if (block.Body is not List<Statement> body)
                throw new InvalidOperationException("Block body not mutable");

            var solutionFile = Path.Combine(TempWorkDir, $"postLine_{postconditionLine}_iter_{StaticCounter.GlobalIteration}_solution.dfy");
            StaticCounter.GlobalIteration += 1;

            ProgramWriter.Write(program, solutionFile, analysis.SuspiciousNodes, postcondition, postconditionLine);

            body.Insert(0, assumeStmt);

            var nextFile = Path.Combine(TempWorkDir, $"postLine_{postconditionLine}_iter_{StaticCounter.GlobalIteration}_next.dfy");
            StaticCounter.GlobalIteration += 1;

            var config = new VerificationConfig
            {
                ProgramFile = nextFile,
                MethodName = "",
                PostCondition = postcondition,
            };

            // Program used in the recursive call!
            ProgramWriter.Write(program, nextFile, new(), postcondition, postconditionLine);

            // Need to remove the mutation to have the program as it was for any other postcondiiotn that failed
            // on other coutnerexample
            body.RemoveAt(0);



            return config;
        }
    }

    static class ProgramWriter
    {
        public static void Write(Microsoft.Dafny.Program program, string path, List<INode> suspicious, string postcondition, int postconditionLine)
        {
            using var writer = new StreamWriter(path);
            var printer = new Printer(writer, program.Options, PrintModes.Everything, null);
            printer.PrintProgram(program, false);

            writer.WriteLine("// ---- Suspicious nodes ----");

            foreach (var node in suspicious)
                writer.WriteLine($"// line {node.StartToken.line}");


            writer.WriteLine($"// Postcondition {postcondition}");
            writer.WriteLine($"// Postcondition Line {postconditionLine}");
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