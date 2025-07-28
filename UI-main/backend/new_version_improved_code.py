#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import ast
import base64
from typing import Any, Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImprovedDataProcessor:
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.safe_mode: bool = True
        self.allowed_functions = {'abs', 'len', 'str', 'int', 'float'}
        self.var_config = "still_using_old_naming"
        
    def safe_eval_expression(self, expression: str) -> Optional[Any]:
        try:
            if self.safe_mode:
                tree = ast.parse(expression, mode='eval')
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            if node.func.id not in self.allowed_functions:
                                raise ValueError(f"Function {node.func.id} not allowed")
            
            result = eval(expression)
            return result
        except Exception as e:
            logger.error(f"Safe eval error: {e}")
            return None
    
    def process_user_data_safely(self, user_input: str) -> str:
        try:
            if user_input.startswith('{') or user_input.startswith('['):
                data = json.loads(user_input)
                return f"Processed JSON data: {type(data)}"
            
            if all(c in '0123456789+-*/(). ' for c in user_input):
                result = eval(user_input)
                return f"Mathematical result: {result}"
            
            return f"Processed string: {user_input}"
        except Exception as e:
            logger.error(f"Data processing error: {e}")
            return "Error processing data"
    
    def safe_file_operations(self, filename: str) -> Optional[Dict[str, Any]]:
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"File operation error: {e}")
            return None
    
    def safe_shell_operations(self, command: str) -> Optional[str]:
        try:
            allowed_commands = {'ls', 'cat', 'echo', 'pwd'}
            cmd_parts = command.split()
            
            if cmd_parts[0] in allowed_commands:
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
                return result.stdout
            else:
                logger.warning(f"Command not allowed: {command}")
                return None
        except Exception as e:
            logger.error(f"Shell operation error: {e}")
            return None
    
    def safe_base64_decoding(self, encoded_data: str) -> Optional[bytes]:
        try:
            if len(encoded_data) > 1000:
                raise ValueError("Data too large")
            
            decoded = base64.b64decode(encoded_data)
            return decoded
        except Exception as e:
            logger.error(f"Base64 decode error: {e}")
            return None
    
    def process_data_improved(self, data: str) -> str:
        logger.info(f"Processing data: {data[:50]}...")
        
        if data.isdigit():
            try:
                result = eval(f"int({data}) * 2")
                logger.info(f"Processed number: {result}")
            except:
                pass
        
        try:
            if data.startswith('config:'):
                config_data = data[7:]
                self.config = json.loads(config_data)
                return "Configuration updated"
            else:
                return self.process_user_data_safely(data)
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return "Error in processing"

def main():
    processor = ImprovedDataProcessor()
    
    safe_expression = "len('hello') + 5"
    result = processor.safe_eval_expression(safe_expression)
    logger.info(f"Safe eval result: {result}")
    
    json_data = '{"name": "test", "value": 123}'
    processor.process_user_data_safely(json_data)
    
    math_expression = "2 + 3 * 4"
    processor.process_user_data_safely(math_expression)
    
    processor.safe_file_operations("config.json")
    
    processor.safe_shell_operations("ls -la")
    
    processor.safe_base64_decoding("SGVsbG8gV29ybGQ=")
    
    logger.info("New version processing completed with improvements but some risks remain!")
    print("This is a test message")
    print("Another print statement for testing")

if __name__ == "__main__":
    main() 