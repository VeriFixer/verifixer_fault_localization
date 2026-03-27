using Microsoft.Dafny;
using DafnyDriver.Commands;
using Microsoft.Boogie;
using System.Text.RegularExpressions;
using System.Text.Json;
using System.Linq;
using System.Diagnostics;


namespace CounterExampleIfReassume
{
    class Program
    {
        private sealed class ProgramArguments
        {
            public string ProgramFile { get; init; } = "";
            public string MethodName { get; init; } = "";
            public string PostCondition { get; init; } = "";
            public int MaxTime { get; init; }
            public int MaxRam { get; init; }
        }

        private static readonly string TempWorkDir = Path.Combine(
            Path.GetTempPath(), "DafnyFaultLocalization_" + Guid.NewGuid());

        static async Task<int> Main(string[] args)
        {
            if (!TryParseArguments(args, out var parsedArguments))
            {
                Console.WriteLine("Usage: program <file.dfy> [method] [postcondition] [--max-time <seconds>] [--max-ram <MB>]");
                return 1;
            }

            // Ensure the temporary directory exists
            Directory.CreateDirectory(TempWorkDir);

            var config = new VerificationConfig
            {
                ProgramFile = parsedArguments.ProgramFile,
                MethodName = parsedArguments.MethodName,
                PostCondition = parsedArguments.PostCondition
            };

            var runner = new VerificationRunner(config, TempWorkDir, parsedArguments.MaxTime, parsedArguments.MaxRam);
            await runner.Run();

            var allSuspiciousLines = await CollectSuspiciousLinesAsync(TempWorkDir);

            WriteJsonOutput(allSuspiciousLines);
            
            Directory.Delete(TempWorkDir, true); 
            return 0;
        }

        private static bool TryParseArguments(string[] args, out ProgramArguments parsedArguments)
        {
            string? programFile = null;
            string methodName = "";
            string postCondition = "";
            int maxTime = 60;
            int maxRam = 24;

            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--max-time" && i + 1 < args.Length)
                {
                    maxTime = int.Parse(args[i + 1]);
                    i++;
                }
                else if (args[i] == "--max-ram" && i + 1 < args.Length)
                {
                    maxRam = int.Parse(args[i + 1]);
                    i++;
                }
                else if (programFile == null)
                {
                    programFile = args[i];
                }
                else if (methodName == "")
                {
                    methodName = args[i];
                }
                else if (postCondition == "")
                {
                    postCondition = args[i];
                }
                else
                {
                    parsedArguments = null!;
                    return false;
                }
            }

            if (string.IsNullOrWhiteSpace(programFile))
            {
                parsedArguments = null!;
                return false;
            }

            parsedArguments = new ProgramArguments
            {
                ProgramFile = programFile,
                MethodName = methodName,
                PostCondition = postCondition,
                MaxTime = maxTime,
                MaxRam = maxRam
            };
            return true;
        }

        private static void WriteJsonOutput(List<List<int>> allSuspiciousLines)
        {
            var json = JsonSerializer.Serialize(allSuspiciousLines);
            Console.WriteLine("JSON_OUTPUT_START");
            Console.WriteLine(json);
            Console.WriteLine("JSON_OUTPUT_END");
        }

        private static async Task<List<List<int>>> CollectSuspiciousLinesAsync(string tempWorkDir)
        {
            var allSuspiciousLines = new List<List<int>>();
            var solutionFiles = Directory.GetFiles(tempWorkDir, "*_solution.dfy");

            foreach (var file in solutionFiles)
            {
                allSuspiciousLines.Add(await ParseSolutionFileAsync(file));
            }

            return allSuspiciousLines;
        }

        private static async Task<List<int>> ParseSolutionFileAsync(string solutionFile)
        {
            var assumeFalseLines = new List<int>();
            var suspiciousLines = new List<int>();
            var lines = await File.ReadAllLinesAsync(solutionFile);
            bool suspiciousSection = false;

            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i];

                if (line.Contains("assume false"))
                {
                    assumeFalseLines.Add(i);
                }

                if (line.Contains("---- Suspicious nodes ----"))
                {
                    suspiciousSection = true;
                    continue;
                }

                if (!suspiciousSection)
                {
                    continue;
                }

                var match = Regex.Match(line, @"// line (\d+)");
                if (match.Success && int.TryParse(match.Groups[1].Value, out int lineNumber))
                {
                    suspiciousLines.Add(ShiftLineNumberForInsertedAssumes(lineNumber, assumeFalseLines));
                    continue;
                }

                if (line.StartsWith("// Postcondition"))
                {
                    suspiciousSection = false;
                }
            }

            return suspiciousLines;
        }

        private static int ShiftLineNumberForInsertedAssumes(int lineNumber, List<int> assumeFalseLines)
        {
            int shiftedLine = lineNumber;
            foreach (var assumeFalseLine in assumeFalseLines)
            {
                if (assumeFalseLine < shiftedLine)
                {
                    shiftedLine -= 1;
                }
            }

            return shiftedLine;
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
        private readonly string TempWorkDir;
        private readonly int maxTime;
        private readonly int maxRam;
        public VerificationRunner(VerificationConfig config, string tempdir, int maxTime, int maxRam)
        {
            this.config = config;
            TempWorkDir = tempdir;
            this.maxTime = maxTime;
            this.maxRam = maxRam;
        }

        public async Task Run()
        {
            Queue<VerificationConfig> verificationQueue = new Queue<VerificationConfig>();

            verificationQueue.Enqueue(config);

            while (verificationQueue.Count > 0)
            {
                var currentConfig = verificationQueue.Dequeue();
                var nextConfigurations = await ProcessConfigAsync(currentConfig);
                foreach (var next in nextConfigurations)
                {
                    verificationQueue.Enqueue(next);
                }
            }
        }

        private async Task<List<VerificationConfig>> ProcessConfigAsync(VerificationConfig currentConfig)
        {
            var options = DafnyOptionsFactory.Create(currentConfig.ProgramFile, maxTime, maxRam);
            var compilation = CliCompilation.Create(options);
            compilation.Start();

            var resolution = await compilation.Resolution
                ?? throw new InvalidOperationException("Resolution failed");
            var resolvedProgram = resolution.ResolvedProgram;

            var failedResults = await CollectFailedResultsAsync(compilation);
            if (failedResults.Count == 0)
            {
                return new List<VerificationConfig>();
            }

            var handler = new VerificationFailureHandler(config, resolvedProgram);
            var nextConfigurations = new List<VerificationConfig>();

            foreach (var fail in failedResults)
            {
                var (nextFiles, _) = await handler.Handle(fail, currentConfig, options, TempWorkDir);
                nextConfigurations.AddRange(nextFiles);
            }

            return nextConfigurations;
        }

        private static async Task<List<CanVerifyResult>> CollectFailedResultsAsync(CliCompilation compilation)
        {
            var failedResults = new List<CanVerifyResult>();
            await foreach (var result in compilation.VerifyAllLazily())
            {
                if (result.Results.Any(r => r.Result.Outcome == SolverOutcome.Invalid))
                {
                    failedResults.Add(result);
                }
            }

            return failedResults;
        }
    }

    class VerificationFailureHandler
    {
        private readonly VerificationConfig config;
        private readonly Microsoft.Dafny.Program program;
        private readonly Microsoft.Dafny.Program TempFolder;

        public VerificationFailureHandler(
            VerificationConfig config,
            Microsoft.Dafny.Program program)
        {
            this.config = config;
            this.program = program;
        }

        public async Task<(List<VerificationConfig>, Boolean)> Handle(CanVerifyResult fail, VerificationConfig programConfig, DafnyOptions options, string TempWorkDir)
        {
            List<VerificationConfig> next_files = new();
            Boolean createdWrites = false;
            var analyzer = new CounterexampleAnalyzer();

            if (fail.CanVerify is not Method method || method.Body == null)
                return (next_files, createdWrites);

            if (!string.IsNullOrEmpty(config.MethodName) &&
                method.Name != config.MethodName)
                return (next_files, createdWrites);

            var statePositions = analyzer.ExtractStatePositionsFromCli(programConfig.ProgramFile);
            var analysis = analyzer.Analyze(statePositions, method.Body);

            // Baseline guarantee: emit at least CLI-extracted state lines even if Dafny task
            // counterexamples are absent for this failing method.
            if (analysis.RawStateLines.Count > 0)
            {
                var baselineMutator = new ProgramMutator(TempWorkDir);
                baselineMutator.writeSolutionNode(program, analysis, "unknown", -1);
                createdWrites = true;
            }


            foreach (var taskResult in fail.Results)
            {
                bool hasCounterexamples = taskResult.Result.CounterExamples.Any();
                if (!hasCounterexamples)
                {
                    continue;
                }

                foreach (var ce in taskResult.Result.CounterExamples)
                {
                    if (analysis.SuspiciousNodes.Count == 0 && analysis.RawStateLines.Count == 0)
                    {
                        continue; // If we cannot find any suspicious node we cannot do much with this counterexample
                    }

                    var postcondition = ce.FailingAssert.ToString();
                    var postconditionLine = ce.FailingAssert.Line;

                    if (programConfig.PostCondition != "" && programConfig.PostCondition != postcondition)
                    {
                        continue; // We only want to expand the same type of error (same failed postcondition)
                    }

                    var mutator = new ProgramMutator(TempWorkDir);

                    mutator.writeSolutionNode(
                        program,
                        analysis,
                        postcondition,
                        postconditionLine);
                    createdWrites = true;
                    
                    if (!analysis.ShouldInject)
                        continue;


                    next_files.Add(await mutator.WriteAssumeFalse(
                        program,
                        analysis,
                        postcondition,
                        postconditionLine));
                }
            }

            return (next_files, createdWrites);
        }
    }

    class CounterexampleAnalyzer
    {
        public sealed class StatePosition
        {
            public int Line { get; init; }
            public int Col { get; init; }
            public string Raw { get; init; } = "";
        }

        public List<StatePosition> ExtractStatePositionsFromCli(string filePath)
        {
            string repoRoot = PathHelper.FindRepoRoot();
            string dafnyBinary = Path.Combine(repoRoot, "dafny", "Binaries", "Dafny");

            var psi = new ProcessStartInfo {
                FileName = dafnyBinary,
                Arguments = $"verify --extract-counterexample \"{filePath}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            if (process == null)
            {
                return [];
            }

            string stdout = process.StandardOutput.ReadToEnd();
            string stderr = process.StandardError.ReadToEnd();
            process.WaitForExit();

            string output = string.IsNullOrWhiteSpace(stderr) ? stdout : stdout + "\n" + stderr;
            var result = new List<StatePosition>();
            var seen = new HashSet<string>();

            bool insideCounterexample = false;
            var positionRegex = new Regex(@"\.dfy\((?<line>\d+),(?<col>\d+)\):", RegexOptions.Compiled);

            foreach (string rawLine in output.Split('\n'))
            {
                string line = rawLine.TrimEnd();

                if (line.Contains("Related counterexample:"))
                {
                    insideCounterexample = true;
                    continue;
                }

                if (!insideCounterexample)
                {
                    continue;
                }

                if (line.Contains("Error:") || line.StartsWith("   |") || line.StartsWith("Dafny program verifier finished"))
                {
                    insideCounterexample = false;
                    continue;
                }

                var match = positionRegex.Match(line);
                if (!match.Success)
                {
                    continue;
                }

                int parsedLine = int.Parse(match.Groups["line"].Value);
                int parsedCol = int.Parse(match.Groups["col"].Value);
                string key = $"{parsedLine}:{parsedCol}";
                if (!seen.Add(key))
                {
                    continue;
                }

                result.Add(new StatePosition {
                    Line = parsedLine,
                    Col = parsedCol,
                    Raw = line.Trim()
                });
            }

            return result;
        }

        public AnalysisResult Analyze(List<StatePosition> statePositions, BlockStmt body)
        {
            if (statePositions.Count == 0)
                return AnalysisResult.Empty;

            var suspiciousNodes = new List<INode>();
            BlockStmt? firstBlockStmt = null;
            bool insideIf = false;

            foreach (var state in statePositions)
            {
                int line = state.Line;
                int col = state.Col;

                var visitor = new FindExpressionAndParentByTokenVisitor(line, col);
                visitor.VisitManual(body);

                if (!visitor.MatchingStatementWithAllParent.Any()) continue;

                var (stmt, parents) = visitor.MatchingStatementWithAllParent[0];

                while (parents.Count > 0)
                {
                    var parent = parents.Pop();
                    if (suspiciousNodes.Contains(parent))
                    {
                        continue;
                    }

                    if (parent is IfStmt ifStmt)
                    {
                        insideIf = true;
                        firstBlockStmt ??= ResolveIfTargetBlock(ifStmt, stmt);
                        suspiciousNodes.Add(parent);
                        break;
                    }

                    if (parent is WhileStmt whileStmt)
                    {
                        insideIf = true;
                        firstBlockStmt ??= whileStmt.Body as BlockStmt;
                        suspiciousNodes.Add(parent);
                        break;
                    }
                }
                suspiciousNodes.Add(stmt);
            }

            var rawStateLines = statePositions.Select(p => p.Line).Distinct().OrderBy(x => x).ToList();
            return new AnalysisResult(insideIf, firstBlockStmt, suspiciousNodes, rawStateLines);
        }

        private static BlockStmt? ResolveIfTargetBlock(IfStmt ifStmt, Statement matchedStatement)
        {
            if (ifStmt.Thn is BlockStmt thenBlock && IsStatementInsideBlock(matchedStatement, thenBlock))
            {
                return thenBlock;
            }

            if (ifStmt.Els is BlockStmt elseBlock && IsStatementInsideBlock(matchedStatement, elseBlock))
            {
                return elseBlock;
            }

            return ifStmt.Thn as BlockStmt;
        }

        private static bool IsStatementInsideBlock(Statement statement, BlockStmt block)
        {
            return block.StartToken.line <= statement.StartToken.line &&
                statement.EndToken.line <= block.EndToken.line;
        }
    }

    class AnalysisResult
    {
        public bool ShouldInject => InsideIf && TargetBlock != null;

        public bool InsideIf { get; }
        public BlockStmt? TargetBlock { get; }
        public List<INode> SuspiciousNodes { get; }
        public List<int> RawStateLines { get; }

        public static AnalysisResult Empty => new(false, null, new(), new());

        public AnalysisResult(bool insideIf, BlockStmt? block, List<INode> nodes, List<int> rawStateLines)
        {
            InsideIf = insideIf;
            TargetBlock = block;
            SuspiciousNodes = nodes;
            RawStateLines = rawStateLines;
        }
    }

    class ProgramMutator
    {
        private readonly string TempWorkDir;
        public ProgramMutator(string tempFolder)
        {
            TempWorkDir = tempFolder;
            if (!Directory.Exists(TempWorkDir))
                Directory.CreateDirectory(TempWorkDir);
        }


        public void writeSolutionNode(
            Microsoft.Dafny.Program program,
            AnalysisResult analysis,
            string postcondition,
            int postconditionLine)
        {
            var solutionFile = Path.Combine(TempWorkDir, $"postLine_{postconditionLine}_iter_{Guid.NewGuid()}_solution.dfy");
            ProgramWriter.Write(program, solutionFile, analysis, postcondition, postconditionLine);
        }



        public async Task<VerificationConfig> WriteAssumeFalse(
            Microsoft.Dafny.Program program,
            AnalysisResult analysis,
            string postcondition,
            int postconditionLine)
        {

            var block = analysis.TargetBlock!;
            // Origin relates source code with position of the token (in this case)
            // We will ignore it shortly afterwards so will just put the block.Origin
            var falseExpr = new Microsoft.Dafny.LiteralExpr(block.Origin, false);
            var assumeStmt = new AssumeStmt(block.Origin, falseExpr, null);

            if (block.Body is not List<Statement> body)
                throw new InvalidOperationException("Block body not mutable");

            body.Insert(0, assumeStmt);

            var nextFile = Path.Combine(TempWorkDir, $"postLine_{postconditionLine}_iter_{Guid.NewGuid()}_next.dfy");

            var config = new VerificationConfig
            {
                ProgramFile = nextFile,
                MethodName = "",
                PostCondition = postcondition,
            };

            // Program used in the recursive call!
            ProgramWriter.Write(program, nextFile, new List<INode>(), postcondition, postconditionLine);

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

        public static void Write(Microsoft.Dafny.Program program, string path, AnalysisResult analysis, string postcondition, int postconditionLine)
        {
            using var writer = new StreamWriter(path);
            var printer = new Printer(writer, program.Options, PrintModes.Everything, null);
            printer.PrintProgram(program, false);

            writer.WriteLine("// ---- Suspicious nodes ----");

            var allLines = new HashSet<int>(analysis.RawStateLines);
            foreach (var node in analysis.SuspiciousNodes)
            {
                allLines.Add(node.StartToken.line);
            }

            foreach (var line in allLines.OrderBy(x => x))
            {
                writer.WriteLine($"// line {line}");
            }

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
            this.targetLine = line;
            this.targetCol = col;
        }

        public override IASTVisitorContext GetContext(IASTVisitorContext context, bool inFunctionPostcondition) => context;

        public void VisitManual(Statement stmt) => VisitStatement(stmt, null);

        protected override void VisitStatement(Statement stmt, IASTVisitorContext context)
        {
            if (IsTargetInStatement(stmt.StartToken, stmt.EndToken))
            {
                if(IsTargetStatement(stmt.StartToken, stmt.EndToken)) {
                    var parentsCopy = new Stack<INode>(parents.Reverse());
                    MatchingStatementWithAllParent.Add((stmt, parentsCopy));
                }

                if(stmt is WhileStmt whilestmt)
                {
                   if(IsTargetInLine(whilestmt.Guard.StartToken, whilestmt.Guard.EndToken))
                    {
                       // Guard want Expressions, but i am working with statements, this breaks things
                       // Woraround will add two times the smtm expresion (and postprocess afterwoards) 
                        var parentsCopy = new Stack<INode>(parents.Reverse());
                        MatchingStatementWithAllParent.Add((stmt, parentsCopy));
                    }
                }
                parents.Push(stmt);
                base.VisitStatement(stmt, context);
                parents.Pop();
            }

        }
        private bool IsTargetInLine(Microsoft.Dafny.Token startToken, Microsoft.Dafny.Token endToken)
        {
            bool lineMatch = startToken.line <= targetLine && targetLine <= endToken.line;
            return lineMatch;
        }
        private bool IsTargetInStatement(Microsoft.Dafny.Token startToken, Microsoft.Dafny.Token endToken)
        {
            bool lineMatch = startToken.line <= targetLine && targetLine <= endToken.line;
            if (!lineMatch)
            {
                return false;
            }

            if(startToken.line == endToken.line)
            {
                bool colMatch = startToken.col <= targetCol && targetCol <= endToken.col;
                return colMatch;
            }
            return true;
        }
        private bool IsTargetStatement(Microsoft.Dafny.Token startToken, Microsoft.Dafny.Token endToken)
        {
            bool lineMatch = startToken.line <= targetLine && targetLine <= endToken.line;
            if (!lineMatch)
            {
                return false;
            }
            if(startToken.line == endToken.line)
            {
                bool colMatch = startToken.col <= targetCol && targetCol <= endToken.col;
                return colMatch;
            }
            return false;
        }
    }
    static class PathHelper
    {
        public static string FindRepoRoot(string marker = ".repo_verifixer_fault_localization_marker")
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
        public static DafnyOptions Create(string filePath, int maxTime, int maxRam)
        {
            string repoRoot = PathHelper.FindRepoRoot();

            var options = new DafnyOptions(Console.In, Console.Out, Console.Error);
            options.ApplyDefaultOptions();

            options.Verify = true;
            options.DafnyVerify = true;
            options.EmitDebugInformation = true;
            options.Compile = false;
            options.DafnyPrelude = Path.Combine(repoRoot, "dafny", "Binaries", "DafnyPrelude.bpl");

            // Set time and memory limits
            options.TimeLimit = (uint)maxTime;
            options.ProverOptions.Add($"O:memory_max_size={maxRam*1000}");

            options.DefiniteAssignmentLevel = 2 ;

            options.Set(CommonOptionBag.AllowWarnings, true);
            options.Set(CommonOptionBag.ExtractCounterexample, true);
            options.Set(BoogieOptionBag.IsolateAssertions, false);
            options.Set(BoogieOptionBag.VerificationErrorLimit, 0);

            options.CliRootSourceUris.Add(new Uri("file://" + Path.GetFullPath(filePath)));
            return options;
        }
    }
}