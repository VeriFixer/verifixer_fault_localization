using Microsoft.Dafny;
using DafnyDriver.Commands;
using Microsoft.Boogie;
using System.Text;

namespace IterativeBranchVerifier
{
    class Program
    {
        static async Task<int> Main(string[] args)
        {
            if (args.Length == 0)
            {
                Console.WriteLine("Usage: program <file.dfy>");
                return 1;
            }

            string currentFilePath = Path.GetFullPath(args[0]);
            bool resolved = false;

            while (!resolved)
            {
                Console.WriteLine($"--- Verifying {Path.GetFileName(currentFilePath)} ---");
                var options = SetupDafnyOptions(currentFilePath);
                var compilation = CliCompilation.Create(options);
                compilation.Start();

                CanVerifyResult? firstFailure = null;
                await foreach (var result in compilation.VerifyAllLazily())
                {
                    if (result.Results.Any(r => r.Result.Outcome == SolverOutcome.Invalid))
                    {
                        firstFailure = result;
                        break; // Process one failure at a time
                    }
                }

                if (firstFailure == null)
                {
                    Console.WriteLine("✅ Verification successful or no more branch failures found.");
                    resolved = true;
                }
                else
                {
                    bool modificationMade = await TryApplyBranchAssumption(firstFailure, currentFilePath, options);
                    if (!modificationMade)
                    {
                        Console.WriteLine("❌ Could not identify a branch to assume postconditions. Stopping.");
                        break;
                    }
                }
            }

            return 0;
        }

        private static async Task<bool> TryApplyBranchAssumption(CanVerifyResult fail, string filePath, DafnyOptions options)
        {
            if (fail.CanVerify is not Method method || method.Body == null) return false;

            // 1. Collect Postconditions (Ensures)
            var postconditions = method.Ensures.Select(e => Printer.ExprToString(options, e.E)).ToList();
            if (!postconditions.Any()) return false;
            string assumeStmt = $"  assume {string.Join(" && ", postconditions)};";

            // 2. Analyze Counterexample to find the branch
            foreach (var taskResult in fail.Results)
            {
                foreach (var ce in taskResult.Result.CounterExamples)
                {
                    if (ce.Model == null) continue;
                    var dafnyModel = new DafnyModel(ce.Model, options);
                    
                    // We look for the last IfStmt encountered in the trace before failure
                    IfStmt? targetIf = null;
                    bool branchDirection = true; // true = then, false = else

                    foreach (var state in dafnyModel.States)
                    {
                        if (!state.StateContainsPosition()) continue;
                        
                        var visitor = new FindExpressionAndParentByTokenVisitor(state.GetLineId(), state.GetCharId());
                        visitor.VisitManual(method.Body);

                        if (visitor.MatchingStatementWithAllParent.Count > 0)
                        {
                            var (stmt, parents) = visitor.MatchingStatementWithAllParent[0];
                            foreach (var parent in parents)
                            {
                                if (parent is IfStmt ifStmt)
                                {
                                    targetIf = ifStmt;
                                    // Determine if we are in the 'Thn' or 'Els' block
                                    branchDirection = IsInBlock(state.GetLineId(), ifStmt.Thn);
                                }
                            }
                        }
                    }

                    if (targetIf != null)
                    {
                        ApplyAssumptionToFile(filePath, targetIf, branchDirection, assumeStmt);
                        return true;
                    }
                }
            }

            return false;
        }

        private static bool IsInBlock(int line, Statement block)
        {
            return line >= block.StartToken.line && line <= block.EndToken.line;
        }

        private static void ApplyAssumptionToFile(string path, IfStmt ifStmt, bool isThenBranch, string assumption)
        {
            var lines = File.ReadAllLines(path).ToList();
            // We want to insert at the end of the block
            int insertLine = isThenBranch ? ifStmt.Thn.EndToken.line : (ifStmt.Els?.EndToken.line ?? ifStmt.Thn.EndToken.line);
            
            // Adjust for 0-based index and insert BEFORE the closing brace
            lines.Insert(insertLine - 1, assumption);
            
            File.WriteAllLines(path, lines);
            Console.WriteLine($"Applied assumption to {(isThenBranch ? "THEN" : "ELSE")} branch at line {insertLine}.");
        }

        private static DafnyOptions SetupDafnyOptions(string filePath)
        {
            var options = new DafnyOptions(Console.In, Console.Out, Console.Error);
            options.ApplyDefaultOptions();
            options.Verify = true;
            options.DafnyVerify = true;
            options.Compile = false;
            options.ModelViewFile = "-";
            options.Set(CommonOptionBag.ExtractCounterexample, true);
            options.CliRootSourceUris.Add(new Uri("file://" + filePath));
            return options;
        }
    }

    // --- Reusing your Visitor Logic with minor cleanup ---
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
            if (stmt.StartToken.line <= targetLine && targetLine <= stmt.EndToken.line)
            {
                var parentsCopy = new Stack<INode>(parents.Reverse()); // Keep correct hierarchy order
                MatchingStatementWithAllParent.Add((stmt, parentsCopy));
            }
            parents.Push(stmt);
            base.VisitStatement(stmt, context);
            parents.Pop();
        }
    }
}