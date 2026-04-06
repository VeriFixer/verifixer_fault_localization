// See https://aka.ms/new-console-template for more information

using Microsoft.Dafny;
using DafnyDriver.Commands;
using Microsoft.Boogie;
using System.Linq;
using System.Text.Json;
using Std.Wrappers;
using System.Diagnostics.Metrics;
using System.Security.Principal;
using System.Diagnostics;
using System.Text.RegularExpressions;


namespace returnMethodLinesRandom
{
    class Program
    {
        private sealed class ProgramArguments
        {
            public string FilePath { get; init; } = "";
            public int MaxTime { get; init; }
            public int MaxRam { get; init; }
        }

        static async Task<int> Main(string[] args)
        {
            if (!TryParseArguments(args, out var parsedArguments))
            {
                Console.WriteLine("Usage: program <file.dfy> [--max-time <seconds>] [--max-ram <MB>]");
                return 1;
            }

            var options = SetupDafnyOptions(parsedArguments.FilePath, parsedArguments.MaxTime, parsedArguments.MaxRam);
            var compilation = CliCompilation.Create(options);
            compilation.Start();

            var failedResults = await CollectFailedResultsAsync(compilation);
            var failedMethodBodies = GetFailedMethodBodies(failedResults);

            int exitCode = await compilation.GetAndReportExitCode();
            var statePositions = ExtractStatePositionsFromCli(parsedArguments.FilePath);
            EmitReportFromCliStates(statePositions, failedMethodBodies);
            return exitCode;
        }

        private static bool TryParseArguments(string[] args, out ProgramArguments parsedArguments)
        {
            string? filePath = null;
            int maxTime = 60;
            int maxRam = 24; // GB

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
                else if (filePath == null)
                {
                    filePath = args[i];
                }
                else
                {
                    parsedArguments = null!;
                    return false;
                }
            }

            if (string.IsNullOrWhiteSpace(filePath))
            {
                parsedArguments = null!;
                return false;
            }

            parsedArguments = new ProgramArguments
            {
                FilePath = filePath,
                MaxTime = maxTime,
                MaxRam = maxRam
            };
            return true;
        }

        private static async Task<List<CanVerifyResult>> CollectFailedResultsAsync(CliCompilation compilation)
        {
            var failedResults = new List<CanVerifyResult>();
            await foreach (var result in compilation.VerifyAllLazily())
            {
                if (result.Results.Any(r => r.Result.Outcome != SolverOutcome.Valid))
                {
                    failedResults.Add(result);
                }
            }

            return failedResults;
        }

        private static List<BlockStmt> GetFailedMethodBodies(List<CanVerifyResult> failedResults)
        {
            return failedResults
                .Select(r => r.CanVerify)
                .OfType<Method>()
                .Where(m => m.Body != null)
                .Select(m => m.Body!)
                .ToList();
        }

        private static DafnyOptions SetupDafnyOptions(string filePath, int maxTime, int maxRam)
        {
            string repoRoot = PathHelper.FindRepoRoot();

            var options = new DafnyOptions(Console.In, Console.Out, Console.Error);
            options.ApplyDefaultOptions();

            options.Verify = true;
            options.DafnyVerify = true;
            options.EmitDebugInformation = true;
            options.Compile = false;
            options.DafnyPrelude = Path.Combine(repoRoot, "dafny", "Binaries", "DafnyPrelude.bpl");

            //options.Define = 2;
            // Set time and memory limits
            options.DefiniteAssignmentLevel = 2;
            options.TimeLimit = (uint)maxTime;
            options.ProverOptions.Add($"O:memory_max_size={maxRam*1000}");

            options.ModelViewFile = "-";
            options.ProverOptions.Add("O:model.completion=true");
            options.ProverOptions.Add("O:model.compact=false");


            options.Set(CommonOptionBag.AllowWarnings, true);
            options.Set(CommonOptionBag.ExtractCounterexample, true);
            // Keep assertions in one VC so model states include intermediate trace positions.
            options.Set(BoogieOptionBag.IsolateAssertions, false);
            options.Set(BoogieOptionBag.VerificationErrorLimit, 0);

            options.CliRootSourceUris.Add(new Uri("file://" + Path.GetFullPath(filePath)));
            return options;
        }

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

        private sealed class StatePosition
        {
            public int Line { get; init; }
            public int Col { get; init; }
            public string Raw { get; init; } = "";
        }

        private static List<StatePosition> ExtractStatePositionsFromCli(string filePath)
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

        private static void EmitReportFromCliStates(List<StatePosition> statePositions, List<BlockStmt> failedMethodBodies)
        {
            var report = new CounterExampleReport();

            for (int traceId = 0; traceId < statePositions.Count; traceId++)
            {
                var state = statePositions[traceId];
                var trace = new CounterExampleTrace { trace_id = traceId };
                trace.nodes.AddRange(AddBranchLogicLines(state.Line, state.Col, state.Raw, failedMethodBodies));
                trace.nodes = trace.nodes.OrderBy(n => n.line).ThenByDescending(n => n.depth).ToList();
                report.traces.Add(trace);
            }

            var jsonOptions = new JsonSerializerOptions { WriteIndented = true };
            string jsonString = JsonSerializer.Serialize(report, jsonOptions);
            Console.WriteLine("JSON_OUTPUT_START");
            Console.WriteLine(jsonString);
            Console.WriteLine("JSON_OUTPUT_END");
        }

        private static List<CounterExampleNode> AddBranchLogicLines(int line, int col, string rawState, List<BlockStmt> failedMethodBodies)
        {
            var branchNodes = new List<CounterExampleNode>();
            var seenBranchKeys = new HashSet<string>();

            foreach (var methodBody in failedMethodBodies)
            {
                if (line < methodBody.StartToken.line || line > methodBody.EndToken.line)
                {
                    continue;
                }

                var visitor = new FindExpressionAndParentByTokenVisitor(line, col);
                visitor.VisitManual(methodBody);
                if (visitor.MatchingStatementWithAllParent.Count == 0)
                {
                    continue;
                }

                var (stmt, parents) = visitor.MatchingStatementWithAllParent[0];
                int matchedDepth = parents.Count + 1;
                var matchedParents = BuildParentRefs(parents);

                branchNodes.Add(new CounterExampleNode
                {
                    line = line,
                    depth = matchedDepth,
                    type = "State",
                    source = "counterexample_state",
                    content = rawState,
                    parents = matchedParents,
                });

                if (stmt is IfStmt || stmt is WhileStmt)
                {
                    string matchedKey = $"{stmt.StartToken.line}:matched_statement:{matchedDepth}";
                    if (seenBranchKeys.Add(matchedKey))
                    {
                        branchNodes.Add(new CounterExampleNode
                        {
                            line = stmt.StartToken.line,
                            depth = matchedDepth,
                            type = stmt is IfStmt ? "IfStmt" : "WhileStmt",
                            source = "matched_statement",
                            content = stmt.ToString(),
                            parents = matchedParents,
                        });
                    }
                }

                int ancestorDepth = parents.Count;
                while (parents.Count > 0)
                {
                    var parent = parents.Pop();
                    var parentParents = BuildParentRefs(parents);
                    if (parent is IfStmt ifStmt)
                    {
                        string key = $"{ifStmt.StartToken.line}:ancestor_chain:{ancestorDepth}";
                        if (seenBranchKeys.Add(key))
                        {
                            branchNodes.Add(new CounterExampleNode
                            {
                                line = ifStmt.StartToken.line,
                                depth = Math.Max(ancestorDepth, 0),
                                type = "IfStmt",
                                source = "ancestor_chain",
                                content = ifStmt.ToString(),
                                parents = parentParents,
                            });
                        }
                    }
                    else if (parent is WhileStmt whileStmt)
                    {
                        string key = $"{whileStmt.StartToken.line}:ancestor_chain:{ancestorDepth}";
                        if (seenBranchKeys.Add(key))
                        {
                            branchNodes.Add(new CounterExampleNode
                            {
                                line = whileStmt.StartToken.line,
                                depth = Math.Max(ancestorDepth, 0),
                                type = "WhileStmt",
                                source = "ancestor_chain",
                                content = whileStmt.ToString(),
                                parents = parentParents,
                            });
                        }
                    }
                    ancestorDepth -= 1;
                }

                break;
            }

            return branchNodes;
        }

        private static List<ParentNodeInfo> BuildParentRefs(Stack<INode> parents)
        {
            var refs = new List<ParentNodeInfo>();
            var parentCopy = new Stack<INode>(parents.Reverse());

            while (parentCopy.Count > 0)
            {
                var parent = parentCopy.Pop();
                refs.Add(new ParentNodeInfo
                {
                    parent_node_type = parent.GetType().Name,
                    parent_node_line = parent.StartToken.line,
                });
            }

            return refs;
        }

    }

    // --- Visitor Implementation ---
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
}

public static class PathHelper
{
    public static string FindRepoRoot(string marker = ".repo_verifixer_fault_localization_marker")
    {
        // Start from the current running assembly directory
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