// See https://aka.ms/new-console-template for more information

using Microsoft.Dafny;
using DafnyDriver.Commands;
using Microsoft.Boogie;
using System.Text.Json;
using Std.Wrappers;
using System.Diagnostics.Metrics;


namespace returnMethodLinesRandom
{
    class Program
    {
        static async Task<int> Main(string[] args)
        {
            string filePath = null;
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
                    Console.WriteLine("Usage: program <file.dfy> [--max-time <seconds>] [--max-ram <MB>]");
                    return 1;
                }
            }
            if (filePath == null)
            {
                Console.WriteLine("Usage: program <file.dfy> [--max-time <seconds>] [--max-ram <MB>]");
                return 1;
            }
            var options = SetupDafnyOptions(filePath, maxTime, maxRam);
            var compilation = CliCompilation.Create(options);
            compilation.Start();

    

            // 1. Collect only the failed results
            var failedResults = new List<CanVerifyResult>();
            await foreach (var result in compilation.VerifyAllLazily())
            {
                if (result.Results.Any(r => r.Result.Outcome != SolverOutcome.Valid))
                {
                    failedResults.Add(result);
                }
            }
            // 2. Process each failure
            foreach (var fail in failedResults)
            {
                ProcessVerificationFailure(fail, options);
            }
            return await compilation.GetAndReportExitCode();
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

            options.CliRootSourceUris.Add(new Uri("file://" + Path.GetFullPath(filePath)));
            return options;
        }

        private static void ProcessVerificationFailure(CanVerifyResult fail, DafnyOptions options)
        {
            // Guard: We only care about methods with bodies
            if (fail.CanVerify is not Method method || method.Body == null) return;

            foreach (var taskResult in fail.Results)
            {
                foreach (var ce in taskResult.Result.CounterExamples)
                {
                    ProcessCounterExample(ce, method.Body, options);
                }
            }
        }

        public class CounterExampleData
        {
            public List<NodeInfo> Nodes { get; set; } = new();
        }

        public class NodeInfo
        {
            public string Type { get; set; }
            public int Line { get; set; }
            public string Content { get; set; } // The actual code string
        }

        private static void ProcessCounterExample(Counterexample ce, BlockStmt methodBody, DafnyOptions options)
        {
            // Data for each counterexample has to be non repeated
            var foundNodes = new List<INode>();
            if (ce.Model == null) return;
            var dafnyModel = new DafnyModel(ce.Model, options);
            foreach (var state in dafnyModel.States)
            {
                // Guard: Skip states without source mapping (like <initial>)
                if (!state.StateContainsPosition()) continue;

                int line = state.GetLineId();
                int col = state.GetCharId();

                var visitor = new FindExpressionAndParentByTokenVisitor(line, col);
                visitor.VisitManual(methodBody);

                if (visitor.MatchingStatementWithAllParent.Count > 0)
                {
                    var (stmt, parents) = visitor.MatchingStatementWithAllParent[0];
                    while (parents.Count > 0)
                    {
                        var currentParent = parents.Pop();
                        if (foundNodes.Contains(currentParent))
                        { continue; }

                        if (currentParent is IfStmt ifStmt || 
                            currentParent is WhileStmt whileStmt){
                            foundNodes.Add(currentParent);
                            break;
                        }
                    }
                    foundNodes.Add(stmt);
                }
            }

            // Save the counterexamples with the if brnaching lines
            var report = new CounterExampleData();
            foreach (var node in foundNodes)
            {
                report.Nodes.Add(new NodeInfo
                {
                    Type = node switch {
                        IfStmt => "IfStmt",
                        WhileStmt => "WhileStmt",
                        _ => "Stmt"
                    }, 
                    Line = node.StartToken.line,
                    Content = node.ToString() // Converts AST node back to source string
                });
            }

            if(foundNodes.Count == 0)
            {
                // This means that the counterexample are only found the method beginning without any node related to it
                // So will add the method beggining line as fall back
                report.Nodes.Add(new NodeInfo
                {
                    Type = "Stmt",
                    Line = methodBody.StartToken.line,
                    Content = "//No node found counterexample only affected start state "
                });
            }
            var jsonOptions = new JsonSerializerOptions { WriteIndented = true };
            string jsonString = JsonSerializer.Serialize(report, jsonOptions);
            Console.WriteLine("```json");
            Console.WriteLine(jsonString);
            Console.WriteLine("```");

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
            if (IsTargetInStatement(stmt))
            {
                var parentsCopy = new Stack<INode>(parents);
                MatchingStatementWithAllParent.Add((stmt, parentsCopy));
            }

            parents.Push(stmt);
            base.VisitStatement(stmt, context);
            parents.Pop();
        }

        private bool IsTargetInStatement(Statement stmt)
        {
            // Simple range check
            bool lineMatch = stmt.StartToken.line <= targetLine && targetLine <= stmt.EndToken.line;
            bool colMatch = stmt.StartToken.col <= targetCol && targetCol <= stmt.EndToken.col;
            return lineMatch && colMatch;
        }
    }
}

public static class PathHelper
{
    public static string FindRepoRoot(string marker = ".repo_verifixer_fault_localizaion_marker")
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