from lexer import Token, Lexer
import sys
import parser as parse


def main(sys.argv):
  with open(sys.argv, "r") as file:
    content = file.read()
  
