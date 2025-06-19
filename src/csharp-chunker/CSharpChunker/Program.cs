using System;
using System.IO;
using System.Threading.Tasks;
using CommandLine;
using Newtonsoft.Json;
using CSharpChunker.Models;

namespace CSharpChunker
{
    public class Options
    {
        [Value(0, MetaName = "input", HelpText = "Input file or directory to process", Required = true)]
        public string Input { get; set; }

        [Option('o', "output", HelpText = "Output JSON file path", Default = "csharp_chunker_output.json")]
        public string Output { get; set; }

        [Option("project-root", HelpText = "Project root directory", Default = ".")]
        public string ProjectRoot { get; set; }
    }

    class Program
    {
        static async Task<int> Main(string[] args)
        {
            return await Parser.Default.ParseArguments<Options>(args)
                .MapResult(
                    async options => await RunChunker(options),
                    errors => Task.FromResult(1)
                );
        }

        static async Task<int> RunChunker(Options options)
        {
            try
            {
                var inputPath = Path.GetFullPath(options.Input);
                var projectRoot = Path.GetFullPath(options.ProjectRoot);

                if (!File.Exists(inputPath) && !Directory.Exists(inputPath))
                {
                    Console.WriteLine($"Input path does not exist: {inputPath}");
                    return 1;
                }

                var chunker = new CSharpCodeChunker(projectRoot);
                ChunkerOutput output;

                if (File.Exists(inputPath))
                {
                    if (Path.GetExtension(inputPath).ToLower() == ".cs")
                    {
                        Console.WriteLine($"Processing C# file: {inputPath}");
                        output = await chunker.ProcessSingleFileAsync(inputPath);
                    }
                    else
                    {
                        Console.WriteLine($"Input file is not a C# file: {inputPath}");
                        return 1;
                    }
                }
                else
                {
                    Console.WriteLine("Directory processing not implemented yet");
                    return 1;
                }

                // Serialize output to JSON
                var json = JsonConvert.SerializeObject(output, Formatting.Indented, new JsonSerializerSettings
                {
                    NullValueHandling = NullValueHandling.Ignore
                });

                await File.WriteAllTextAsync(options.Output, json);

                Console.WriteLine($"C# chunker completed. Output written to: {options.Output}");
                Console.WriteLine($"Processed {output.ProcessedFiles.Count} files, extracted {output.Nodes.Count} nodes, {output.Relationships.Count} relationships");

                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
                Console.WriteLine($"Stack trace: {ex.StackTrace}");
                return 1;
            }
        }
    }
} 