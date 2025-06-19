#!/usr/bin/env node
/**
 * NodeJS/TypeScript Code Chunker for Agentic Code Indexer
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { glob } from 'glob';
import { Command } from 'commander';
import * as acorn from 'acorn';

import {
    ChunkerOutput, AnyNode, Relationship, FileNode,
    NodeType, RelationshipType
} from './types';

class NodeJSChunker {
    private projectRoot: string;
    private nodes: AnyNode[] = [];
    private relationships: Relationship[] = [];
    private processedFiles: string[] = [];
    private nodeCounter = 0;

    constructor(projectRoot: string) {
        this.projectRoot = path.resolve(projectRoot);
    }

    private generateNodeId(prefix: string = 'node'): string {
        this.nodeCounter++;
        return `${prefix}_${this.nodeCounter}`;
    }

    private calculateChecksum(content: string): string {
        return crypto.createHash('sha256').update(content, 'utf8').hexdigest();
    }

    private getRelativePath(filePath: string): string {
        return path.relative(this.projectRoot, filePath);
    }

    private createFileNode(filePath: string, content: string, language: string): FileNode {
        const stats = fs.statSync(filePath);
        
        return {
            id: this.generateNodeId('file'),
            label: NodeType.FILE,
            name: path.basename(filePath),
            full_name: this.getRelativePath(filePath),
            path: this.getRelativePath(filePath),
            absolute_path: filePath,
            extension: path.extname(filePath),
            size: stats.size,
            checksum: this.calculateChecksum(content),
            content: content,
            language: language
        };
    }

    public async processFile(filePath: string): Promise<void> {
        try {
            console.log(`Processing file: ${filePath}`);
            
            const content = fs.readFileSync(filePath, 'utf8');
            const ext = path.extname(filePath).toLowerCase();
            
            // Create file node
            const language = ext === '.ts' || ext === '.tsx' ? 'typescript' : 'javascript';
            const fileNode = this.createFileNode(filePath, content, language);
            this.nodes.push(fileNode);
            
            this.processedFiles.push(filePath);
            
        } catch (error) {
            console.error(`Error processing file ${filePath}:`, error);
        }
    }

    public getOutput(): ChunkerOutput {
        return {
            language: 'javascript-typescript',
            version: '1.0.0',
            processed_files: this.processedFiles,
            nodes: this.nodes,
            relationships: this.relationships,
            metadata: {
                total_files: this.processedFiles.length,
                total_nodes: this.nodes.length,
                total_relationships: this.relationships.length
            }
        };
    }
}

async function main() {
    const program = new Command();
    
    program
        .name('nodejs-chunker')
        .description('NodeJS/TypeScript Code Chunker for Agentic Code Indexer')
        .version('1.0.0');

    program
        .argument('<input>', 'Input file or directory to process')
        .option('-o, --output <file>', 'Output JSON file', 'nodejs_chunker_output.json')
        .option('--project-root <dir>', 'Project root directory', '.')
        .action(async (input, options) => {
            const inputPath = path.resolve(input);
            const projectRoot = path.resolve(options.projectRoot);
            
            if (!fs.existsSync(inputPath)) {
                console.error(`Input path does not exist: ${inputPath}`);
                process.exit(1);
            }

            const chunker = new NodeJSChunker(projectRoot);
            
            const stats = fs.statSync(inputPath);
            if (stats.isFile()) {
                await chunker.processFile(inputPath);
            } else {
                console.error(`Directory processing not implemented yet`);
                process.exit(1);
            }

            const output = chunker.getOutput();
            
            fs.writeFileSync(options.output, JSON.stringify(output, null, 2));
            
            console.log(`NodeJS chunker completed. Output written to: ${options.output}`);
        });

    await program.parseAsync();
}

if (require.main === module) {
    main().catch(console.error);
} 