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
        public class CounterExampleReport
        {
            public List<CounterExampleTrace> traces { get; set; } = new();
        }

        public class CounterExampleTrace
        {
            public int trace_id { get; set; }
            public List<CounterExampleNode> nodes { get; set; } = new();
        }

        public class ParentNodeInfo
        {
            public string parent_node_type { get; set; } = "";
            public int parent_node_line { get; set; }
        }

        public class CounterExampleNode
        {
            public int line { get; set; }
            public int depth { get; set; }
            public string type { get; set; } = "";
            public string source { get; set; } = "";
            public string content { get; set; } = "";
            public List<ParentNodeInfo> parents { get; set; } = new();
        }

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

            var report = await CollectSuspiciousLinesAsync(TempWorkDir);

            WriteJsonOutput(report);

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

        private static void WriteJsonOutput(CounterExampleReport report)
        {
            var json = JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true });
            Console.WriteLine("JSON_OUTPUT_START");
            Console.WriteLine(json);
            Console.WriteLine("JSON_OUTPUT_END");
        }

        private static async Task<CounterExampleReport> CollectSuspiciousLinesAsync(string tempWorkDir)
        {
            var report = new CounterExampleReport();
            var solutionFiles = Directory.GetFiles(tempWorkDir, "*_solution.dfy");

            int traceId = 0;
            foreach (var file in solutionFiles)
            {
                var trace = await ParseSolutionFileAsync(file, traceId);
                report.traces.Add(trace);
                traceId += 1;
            }

            return report;
        }

        private static async Task<CounterExampleTrace> ParseSolutionFileAsync(string solutionFile, int traceId)
        {
            var trace = new CounterExampleTrace { trace_id = traceId };
            var assumeFalseLines = new List<int>();
            var lines = await File.ReadAllLinesAsync(solutionFile);
            bool suspiciousSection = false;

            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i];

                if (!suspiciousSection && IsAssumeFalseCodeLine(line))
                {
                    // Keep 1-based indexing to match Dafny token line numbers.
                    assumeFalseLines.Add(i + 1);
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

                if (line.StartsWith("// node "))
                {
                    var rawJson = line.Substring("// node ".Length);
                    try
                    {
                        var parsed = JsonSerializer.Deserialize<CounterExampleNode>(rawJson);
                        if (parsed != null)
                        {
                            parsed.line = ShiftLineNumberForInsertedAssumes(parsed.line, assumeFalseLines);
                            foreach (var parent in parsed.parents)
                            {
                                parent.parent_node_line = ShiftLineNumberForInsertedAssumes(
                                    parent.parent_node_line,
                                    assumeFalseLines
                                );
                            }
                            trace.nodes.Add(parsed);
                        }
                    }
                    catch (JsonException)
                    {
                        // Ignore malformed node lines and continue parsing.
                    }
                    continue;
                }

                if (line.StartsWith("// Postcondition"))
                {
                    suspiciousSection = false;
                }
            }

            return trace;
        }

        private static bool IsAssumeFalseCodeLine(string line)
        {
            var trimmed = line.TrimStart();
            if (trimmed.StartsWith("//"))
            {
                return false;
            }

            return Regex.IsMatch(trimmed, @"\bassume\s+false\b");
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
        public string ProgramFile { get; init; } = string.Empty;
        public string MethodName { get; init; } = string.Empty;
        public string PostCondition { get; init; } = string.Empty;
        public int PostConditionLine { get; init; } = -1;
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
                var (nextFiles, _) = await handler.Handle(fail, currentConfig, TempWorkDir);
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

        public VerificationFailureHandler(
            VerificationConfig config,
            Microsoft.Dafny.Program program)
        {
            this.config = config;
            this.program = program;
        }

        public async Task<(List<VerificationConfig>, Boolean)> Handle(CanVerifyResult fail, VerificationConfig programConfig, string TempWorkDir)
        {
            List<VerificationConfig> next_files = new();
            Boolean createdWrites = false;
            var analyzer = new CounterexampleAnalyzer();

            if (fail.CanVerify is not Method method || method.Body == null)
                return (next_files, createdWrites);

            if (!string.IsNullOrEmpty(config.MethodName) &&
                method.Name != config.MethodName)
                return (next_files, createdWrites);

            var counterExamples = analyzer.ExtractCounterExamplesFromCli(programConfig.ProgramFile);

            foreach (var counterExample in counterExamples)
            {
                if (!ShouldProcessCounterExample(programConfig, counterExample))
                {
                    continue;
                }

                var analysis = analyzer.Analyze(counterExample.StatePositions, method.Body);

                if (analysis.SuspiciousNodes.Count == 0 && analysis.RawStateLines.Count == 0)
                {
                    continue;
                }

                if (counterExample.PostconditionLine <= 0)
                {
                    Console.Error.WriteLine("[Handle] Skipping counterexample because Dafny did not provide a valid postcondition line.");
                    continue;
                }

                var postcondition = counterExample.PostconditionText;
                var mutator = new ProgramMutator(TempWorkDir);

                mutator.writeSolutionNode(
                    program,
                    analysis,
                    postcondition,
                    counterExample.PostconditionLine);
                createdWrites = true;

                if (!analysis.ShouldInject)
                    continue;

                var nextConfig = await mutator.WriteAssumeFalse(
                    program,
                    programConfig.ProgramFile,
                    analysis,
                    postcondition,
                    counterExample.PostconditionLine);

                if (nextConfig != null)
                {
                    next_files.Add(nextConfig);
                }
            }

            return (next_files, createdWrites);
        }

        private static bool ShouldProcessCounterExample(
            VerificationConfig programConfig,
            CounterexampleAnalyzer.CliCounterExample counterExample)
        {
            if (programConfig.PostConditionLine > 0)
            {
                return programConfig.PostConditionLine == counterExample.PostconditionLine;
            }

            if (string.IsNullOrWhiteSpace(programConfig.PostCondition))
            {
                return true;
            }

            return NormalizePostCondition(programConfig.PostCondition) ==
                NormalizePostCondition(counterExample.PostconditionText);
        }

        private static string NormalizePostCondition(string text)
        {
            return Regex.Replace(text ?? string.Empty, @"\s+", " ").Trim();
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

        private static string ReadSourceLine(string[] sourceLines, int lineNumber)
        {
            if (lineNumber <= 0 || lineNumber > sourceLines.Length)
            {
                return string.Empty;
            }

            return sourceLines[lineNumber - 1].Trim();
        }

        public sealed class CliCounterExample
        {
            public int PostconditionLine { get; init; }
            public string PostconditionText { get; init; } = string.Empty;
            public List<StatePosition> StatePositions { get; init; } = new();
        }

        public List<CliCounterExample> ExtractCounterExamplesFromCli(string filePath)
        {
            string repoRoot = PathHelper.FindRepoRoot();
            string dafnyBinary = Path.Combine(repoRoot, "dafny", "Binaries", "Dafny");
            var sourceLines = File.ReadAllLines(filePath);

            var psi = new ProcessStartInfo
            {
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
            var result = new List<CliCounterExample>();
            var currentStates = new List<StatePosition>();
            var seen = new HashSet<string>();
            int currentPostconditionLine = -1;
            string currentPostconditionText = string.Empty;

            bool insideCounterexample = false;
            bool sawRelatedCounterexample = false;
            bool sawPostconditionLocation = false;
            var positionRegex = new Regex(@"\.dfy\((?<line>\d+),(?<col>\d+)\):", RegexOptions.Compiled);
            var postconditionRegex = new Regex(@"\.dfy\((?<line>\d+),(?<col>\d+)\):\s*Related location:", RegexOptions.Compiled);

            void FinalizeCurrentRecord()
            {
                if (currentPostconditionLine <= 0 && currentStates.Count > 0)
                {
                    // Fallback for verifier outputs that omit an explicit
                    // postcondition location but still provide state locations.
                    currentPostconditionLine = currentStates[0].Line;
                    currentPostconditionText = ReadSourceLine(sourceLines, currentPostconditionLine);
                }

                if (currentPostconditionLine <= 0)
                {
                    currentStates.Clear();
                    currentPostconditionText = string.Empty;
                    sawRelatedCounterexample = false;
                    sawPostconditionLocation = false;
                    return;
                }

                result.Add(new CliCounterExample
                {
                    PostconditionLine = currentPostconditionLine,
                    PostconditionText = currentPostconditionText,
                    StatePositions = new List<StatePosition>(currentStates)
                });

                currentStates.Clear();
                currentPostconditionLine = -1;
                currentPostconditionText = string.Empty;
                sawRelatedCounterexample = false;
                sawPostconditionLocation = false;
                seen.Clear();
            }

            foreach (string rawLine in output.Split('\n'))
            {
                string line = rawLine.TrimEnd();

                if (line.Contains("Error: a postcondition could not be proved on this return path"))
                {
                    FinalizeCurrentRecord();
                    insideCounterexample = false;
                    continue;
                }

                if (line.Contains("Related counterexample:"))
                {
                    insideCounterexample = true;
                    sawRelatedCounterexample = true;
                    continue;
                }

                if (!insideCounterexample)
                {
                    continue;
                }

                if (line.StartsWith("Dafny program verifier finished"))
                {
                    FinalizeCurrentRecord();
                    insideCounterexample = false;
                    continue;
                }

                if (postconditionRegex.IsMatch(line))
                {
                    var postconditionMatch = postconditionRegex.Match(line);
                    currentPostconditionLine = int.Parse(postconditionMatch.Groups["line"].Value);
                    currentPostconditionText = ReadSourceLine(sourceLines, currentPostconditionLine);
                    sawPostconditionLocation = true;
                    continue;
                }

                var positionMatch = positionRegex.Match(line);
                if (!positionMatch.Success)
                {
                    continue;
                }

                int parsedLine = int.Parse(positionMatch.Groups["line"].Value);
                int parsedCol = int.Parse(positionMatch.Groups["col"].Value);
                string key = $"{parsedLine}:{parsedCol}";
                if (!seen.Add(key))
                {
                    continue;
                }

                currentStates.Add(new StatePosition
                {
                    Line = parsedLine,
                    Col = parsedCol,
                    Raw = line.Trim()
                });
            }

            if (sawRelatedCounterexample && sawPostconditionLocation)
            {
                FinalizeCurrentRecord();
            }

            return result;
        }

        public AnalysisResult Analyze(List<StatePosition> statePositions, BlockStmt body)
        {
            if (statePositions.Count == 0)
                return AnalysisResult.Empty;

            var suspiciousNodes = new List<AnalysisResult.SuspiciousNodeInfo>();
            var seenSuspicious = new HashSet<string>();
            BlockStmt? firstBlockStmt = null;
            bool insideIf = false;

            foreach (var state in statePositions)
            {
                int line = state.Line;
                int col = state.Col;

                var visitor = new FindExpressionAndParentByTokenVisitor(line, col);
                visitor.VisitManual(body);

                if (!visitor.MatchingStatementWithAllParent.Any())
                {
                    AppendStateNodeIfMissing(state, seenSuspicious, suspiciousNodes);
                    continue;
                }

                var (stmt, parents) = visitor.MatchingStatementWithAllParent[0];
                int matchedDepth = parents.Count + 1;

                string matchedType = stmt switch
                {
                    IfStmt => "IfStmt",
                    WhileStmt => "WhileStmt",
                    _ => "Statement",
                };

                string matchedKey = $"{stmt.StartToken.line}:{matchedDepth}:matched_statement:{matchedType}";
                if (seenSuspicious.Add(matchedKey))
                {
                    suspiciousNodes.Add(new AnalysisResult.SuspiciousNodeInfo
                    {
                        Line = stmt.StartToken.line,
                        Depth = matchedDepth,
                        Type = matchedType,
                        Source = "matched_statement",
                        Content = stmt.ToString(),
                        Parents = BuildParentRefs(parents),
                    });
                }

                int ancestorDepth = parents.Count;
                while (parents.Count > 0)
                {
                    var parent = parents.Pop();
                    var parentRefs = BuildParentRefs(parents);
                    if (parent is IfStmt ifStmt)
                    {
                        insideIf = true;
                        firstBlockStmt ??= ResolveIfTargetBlock(ifStmt, stmt);
                        string key = $"{ifStmt.StartToken.line}:{ancestorDepth}:ancestor_chain:IfStmt";
                        if (seenSuspicious.Add(key))
                        {
                            suspiciousNodes.Add(new AnalysisResult.SuspiciousNodeInfo
                            {
                                Line = ifStmt.StartToken.line,
                                Depth = Math.Max(ancestorDepth, 0),
                                Type = "IfStmt",
                                Source = "ancestor_chain",
                                Content = ifStmt.ToString(),
                                Parents = parentRefs,
                            });
                        }
                    }

                    else if (parent is WhileStmt whileStmt)
                    {
                        insideIf = true;
                        firstBlockStmt ??= whileStmt.Body as BlockStmt;
                        string key = $"{whileStmt.StartToken.line}:{ancestorDepth}:ancestor_chain:WhileStmt";
                        if (seenSuspicious.Add(key))
                        {
                            suspiciousNodes.Add(new AnalysisResult.SuspiciousNodeInfo
                            {
                                Line = whileStmt.StartToken.line,
                                Depth = Math.Max(ancestorDepth, 0),
                                Type = "WhileStmt",
                                Source = "ancestor_chain",
                                Content = whileStmt.ToString(),
                                Parents = parentRefs,
                            });
                        }
                    }
                    ancestorDepth -= 1;
                }

                AppendStateNodeIfMissing(state, seenSuspicious, suspiciousNodes);
            }

            var rawStateLines = statePositions.Select(p => p.Line).Distinct().OrderBy(x => x).ToList();
            return new AnalysisResult(insideIf, firstBlockStmt, suspiciousNodes, rawStateLines);
        }

        private static void AppendStateNodeIfMissing(
            StatePosition state,
            HashSet<string> seenSuspicious,
            List<AnalysisResult.SuspiciousNodeInfo> suspiciousNodes)
        {
            string stateKey = $"{state.Line}:0:counterexample_state:State";
            if (!seenSuspicious.Add(stateKey))
            {
                return;
            }

            suspiciousNodes.Add(new AnalysisResult.SuspiciousNodeInfo
            {
                Line = state.Line,
                Depth = 0,
                Type = "State",
                Source = "counterexample_state",
                Content = state.Raw,
                Parents = new List<Program.ParentNodeInfo>(),
            });
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

        private static List<Program.ParentNodeInfo> BuildParentRefs(Stack<INode> parents)
        {
            var refs = new List<Program.ParentNodeInfo>();
            var parentCopy = new Stack<INode>(parents.Reverse());

            while (parentCopy.Count > 0)
            {
                var parent = parentCopy.Pop();
                refs.Add(new Program.ParentNodeInfo
                {
                    parent_node_type = parent.GetType().Name,
                    parent_node_line = parent.StartToken.line,
                });
            }

            return refs;
        }
    }

    class AnalysisResult
    {
        public class SuspiciousNodeInfo
        {
            public int Line { get; init; }
            public int Depth { get; init; }
            public string Type { get; init; } = "";
            public string Source { get; init; } = "";
            public string Content { get; init; } = "";
            public List<Program.ParentNodeInfo> Parents { get; init; } = new();
        }

        public bool ShouldInject => InsideIf && TargetBlock != null;

        public bool InsideIf { get; }
        public BlockStmt? TargetBlock { get; }
        public List<SuspiciousNodeInfo> SuspiciousNodes { get; }
        public List<int> RawStateLines { get; }

        public static AnalysisResult Empty => new(false, null, new(), new());

        public AnalysisResult(bool insideIf, BlockStmt? block, List<SuspiciousNodeInfo> nodes, List<int> rawStateLines)
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
            if (postconditionLine <= 0)
            {
                Console.Error.WriteLine("[writeSolutionNode] Refusing to write solution node with invalid postcondition line.");
                return;
            }

            var solutionFile = Path.Combine(TempWorkDir, $"postLine_{postconditionLine}_iter_{Guid.NewGuid()}_solution.dfy");
            ProgramWriter.Write(program, solutionFile, analysis, postcondition, postconditionLine);
        }



        public async Task<VerificationConfig?> WriteAssumeFalse(
            Microsoft.Dafny.Program program,
            string sourceProgramFile,
            AnalysisResult analysis,
            string postcondition,
            int postconditionLine)
        {
            if (!File.Exists(sourceProgramFile))
            {
                Console.Error.WriteLine($"[WriteAssumeFalse] Source file not found: {sourceProgramFile}");
                return null;
            }

            var sourceText = await File.ReadAllTextAsync(sourceProgramFile);
            var sourceAssumeFalseCount = CountAssumeFalseOccurrences(sourceText);

            var block = analysis.TargetBlock!;
            // Origin relates source code with position of the token (in this case)
            // We will ignore it shortly afterwards so will just put the block.Origin
            var falseExpr = new Microsoft.Dafny.LiteralExpr(block.Origin, false);
            var assumeStmt = new AssumeStmt(block.Origin, falseExpr, null);

            if (block.Body is not List<Statement> body)
                throw new InvalidOperationException("Block body not mutable");

            var nextFile = Path.Combine(TempWorkDir, $"postLine_{postconditionLine}_iter_{Guid.NewGuid()}_next.dfy");

            body.Insert(0, assumeStmt);
            try
            {
                // Program used in the recursive call.
                ProgramWriter.Write(program, nextFile, new List<INode>(), postcondition, postconditionLine);
            }
            finally
            {
                // Keep the in-memory AST unchanged for subsequent mutations.
                body.RemoveAt(0);
            }

            var nextText = await File.ReadAllTextAsync(nextFile);
            var nextAssumeFalseCount = CountAssumeFalseOccurrences(nextText);

            if (sourceText == nextText)
            {
                Console.Error.WriteLine(
                    $"[WriteAssumeFalse] Skipping next file because no change was produced: {nextFile}");
                File.Delete(nextFile);
                return null;
            }

            if (nextAssumeFalseCount <= sourceAssumeFalseCount)
            {
                Console.Error.WriteLine(
                    "[WriteAssumeFalse] Skipping next file because 'assume false' was not added. " +
                    $"source={sourceAssumeFalseCount}, next={nextAssumeFalseCount}, file={nextFile}");
                File.Delete(nextFile);
                return null;
            }

            return new VerificationConfig
            {
                ProgramFile = nextFile,
                MethodName = "",
                PostCondition = postcondition,
                PostConditionLine = postconditionLine,
            };
        }

        private static int CountAssumeFalseOccurrences(string text)
        {
            return Regex.Matches(text, @"\bassume\s+false\b").Count;
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

            foreach (var node in analysis.SuspiciousNodes)
            {
                var nodePayload = new Program.CounterExampleNode
                {
                    line = node.Line,
                    depth = node.Depth,
                    type = node.Type,
                    source = node.Source,
                    content = node.Content,
                    parents = node.Parents,
                };
                writer.WriteLine($"// node {JsonSerializer.Serialize(nodePayload)}");
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

        public void VisitManual(Statement stmt) => VisitStatement(stmt, null!);

        protected override void VisitStatement(Statement stmt, IASTVisitorContext context)
        {
            if (IsTargetInStatement(stmt.StartToken, stmt.EndToken))
            {
                if (IsTargetStatement(stmt.StartToken, stmt.EndToken))
                {
                    var parentsCopy = new Stack<INode>(parents.Reverse());
                    MatchingStatementWithAllParent.Add((stmt, parentsCopy));
                }

                if (stmt is WhileStmt whilestmt)
                {
                    if (whilestmt.Guard != null && IsTargetInLine(whilestmt.Guard.StartToken, whilestmt.Guard.EndToken))
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

            if (startToken.line == endToken.line)
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
            if (startToken.line == endToken.line)
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
            options.ProverOptions.Add($"O:memory_max_size={maxRam * 1000}");

            options.DefiniteAssignmentLevel = 2;

            options.Set(CommonOptionBag.AllowWarnings, true);
            options.Set(CommonOptionBag.ExtractCounterexample, true);
            options.Set(BoogieOptionBag.IsolateAssertions, false);
            options.Set(BoogieOptionBag.VerificationErrorLimit, 0);

            options.CliRootSourceUris.Add(new Uri("file://" + Path.GetFullPath(filePath)));
            return options;
        }
    }
}