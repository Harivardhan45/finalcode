#!/usr/bin/env python3

import os
import sys
import subprocess
import pickle
import marshal
import base64

class RiskyDataProcessor:
    def __init__(self):
        self.dynamic_code = "print('Hello from eval!')"
        self.user_input = "os.system('rm -rf /')"
        self.global_vars = globals()
        self.var_data = "old_style_variable"
        
    def process_user_data(self, user_input):
        try:
            result = eval(user_input)
            return result
        except Exception as e:
            print(f"Error in eval: {e}")
            return None
    
    def execute_dynamic_code(self, code_string):
        try:
            exec(code_string)
        except Exception as e:
            print(f"Error in exec: {e}")
    
    def unsafe_file_operations(self, filename):
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            
            with open(filename, 'rb') as f:
                marshaled_data = marshal.load(f)
                
            return data, marshaled_data
        except Exception as e:
            print(f"File operation error: {e}")
            return None, None
    
    def unsafe_shell_operations(self, command):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            print(f"Shell operation error: {e}")
            return None
    
    def unsafe_base64_decoding(self, encoded_data):
        try:
            decoded = base64.b64decode(encoded_data)
            return decoded
        except Exception as e:
            print(f"Base64 decode error: {e}")
            return None
    
    def process_data_with_risks(self, data):
        if 'process_user_data' in globals():
            result = globals()['process_user_data'](data)
        
        if isinstance(data, str):
            try:
                evaluated = eval(data)
                print(f"Evaluated result: {evaluated}")
            except:
                pass
        
        if data.startswith('print'):
            try:
                exec(data)
            except:
                pass
        
        return "Processed with risks"

def main():
    processor = RiskyDataProcessor()
    
    user_code = input("Enter some code to evaluate: ")
    processor.process_user_data(user_code)
    
    dynamic_code = "print('This code was executed dynamically!')"
    processor.execute_dynamic_code(dynamic_code)
    
    processor.unsafe_file_operations("suspicious_file.pkl")
    
    processor.unsafe_shell_operations("ls -la")
    
    processor.unsafe_base64_decoding("SGVsbG8gV29ybGQ=")
    
    print("Old version processing completed with multiple risks!")
    print("This is a test message")
    print("Another print statement for testing")

if __name__ == "__main__":
    main() 