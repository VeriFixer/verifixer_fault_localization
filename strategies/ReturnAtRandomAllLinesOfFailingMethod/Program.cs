// See https://aka.ms/new-console-template for more information

using Microsoft.Dafny;
using DafnyDriver.Commands;
using Microsoft.Boogie;

namespace returnMethodLinesRandom
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

            var filename = Path.GetFullPath(args[0]);

            var options = new DafnyOptions(Console.In, Console.Out, Console.Error);
            options.ApplyDefaultOptions();

            options.Verify = true;
            options.EmitDebugInformation = true;
            options.Compile = false;
            options.DafnyVerify = true;

            string repoRoot = PathHelper.FindRepoRoot();
            options.DafnyPrelude = Path.Combine(repoRoot, "dafny", "Binaries", "DafnyPrelude.bpl");
            options.FailOnWarnings = false;
            options.AllowSourceFolders = true;
            options.Set(CommonOptionBag.AllowWarnings, true);

            options.CliRootSourceUris.Add(new Uri("file://" + filename));


            var compilation = CliCompilation.Create(options);

            compilation.Start();

            var fails = new List<CanVerifyResult>();

            await foreach (var result in compilation.VerifyAllLazily())
            {
                foreach (var taskResult in result.Results)
                {
                    if (taskResult.Result.Outcome == Microsoft.Boogie.SolverOutcome.Invalid)
                    {
                        fails.Add(result);
                    }
                }
            }
            foreach (var fail in fails)
            {
                if (fail.CanVerify is Method method)
                {
                    var body = method.Body;
                    if (body != null)
                    {
                        var startTok = body.StartToken;
                        var endTok = body.EndToken;
                        var startLine = startTok.line;
                        var endLine = endTok.line;
                        Console.WriteLine($"Method '{method.Name}': spans lines {startLine} to {endLine}");
                    }
                }
            }
            var exitCode = await compilation.GetAndReportExitCode();
            return exitCode;
        }
    }


    //    class MainReturnValTest
    //    {
    //        static async Task<int> Main(string[] args)
    //        {
    //            TextWriter error = Console.Error;
    //            TextWriter output = Console.Out;
    //            TextReader input = Console.In;
    //
    //            DafnyOptions options = new DafnyOptions(input, output, error);
    //
    //            var reporter = new ConsoleErrorReporter(options);
    //            string mFile;
    //            if (args.Length < 1)
    //            {
    //                Console.WriteLine("Usage: Program <file>");
    //                return 0;
    //            }
    //            mFile = Path.GetFullPath(args[0]);
    //
    //            // CHANGE 3: Use 'file://' or actual local paths for the URI
    //            var uri = new Uri("file://" + mFile);
    //
    //            // CHANGE 4: Replace the missing 'AddFilesToFs' logic
    //            var filesDict = new Dictionary<Uri, string> { { uri, File.ReadAllText(mFile) } };
    //            var fs = new InMemoryFileSystem(filesDict);
    //            var files = new List<DafnyFile>();
    //
    //            foreach (var dafnyElement in filesDict)
    //            {
    //                var asyncFiles = DafnyFile.CreateAndValidate(
    //                    fs,
    //                    reporter,
    //                    options,
    //                    dafnyElement.Key,
    //                    Token.NoToken
    //                );
    //
    //                foreach (var file in asyncFiles.ToBlockingEnumerable()) 
    //                {
    //                    files.Add(file);
    //                }
    //            }
    //
    //            var logger = NullLogger<ProgramParser>.Instance;
    //            var parser = new ProgramParser(logger, fs);
    //            // CHANGE 5: Pass the correct 'mFile' variable here
    //            ProgramParseResult parseResult = await parser.ParseFiles(
    //                mFile, 
    //                files,
    //                reporter,
    //                CancellationToken.None
    //            );
    //
    //            var program = parseResult.Program;
    //            var resolver = new ProgramResolver(program);
    //
    //            await resolver.Resolve(CancellationToken.None);
    //
    //            if (reporter.HasErrors)
    //            {
    //                Console.WriteLine($"Error count: {reporter.ErrorCount}");
    //                // Handle errors...
    //                return 1;
    //            }
    //            Console.WriteLine("Successfully parsed and resolved!");
    //
    //
    //           if (reporter.HasErrors) {
    //    Console.WriteLine($"Verification failed with {reporter.ErrorCount} error(s).");
    //    // (The errors themselves have already been written to reporter, e.g. Console.Error)
    //    return 1;
    //}
    //Console.WriteLine("Verification succeeded!");
    //            return 0;
    //        }
    //    }
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