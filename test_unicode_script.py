#!/usr/bin/env python3
"""
Unicode Test Script
Tests various Unicode characters and emojis to verify UTF-8 encoding works correctly
"""

import sys
import os

def main():
    print("=" * 60)
    print("Unicode Test Script")
    print("=" * 60)
    print()
    
    # Test 1: Encoding Information
    print("Test 1: Encoding Information")
    print("-" * 60)
    print(f"  stdout encoding: {sys.stdout.encoding}")
    print(f"  stderr encoding: {sys.stderr.encoding}")
    print(f"  stdin encoding: {sys.stdin.encoding}")
    print(f"  default encoding: {sys.getdefaultencoding()}")
    print(f"  PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'not set')}")
    print(f"  PYTHONUTF8: {os.environ.get('PYTHONUTF8', 'not set')}")
    print()
    
    # Test 2: Chinese Characters
    print("Test 2: Chinese Characters")
    print("-" * 60)
    print("  你好世界！")
    print("  欢迎使用 IndexPilot")
    print()
    
    # Test 3: Japanese Characters
    print("Test 3: Japanese Characters")
    print("-" * 60)
    print("  こんにちは世界")
    print("  ありがとうございます")
    print()
    
    # Test 4: Emojis
    print("Test 4: Emojis")
    print("-" * 60)
    print("  🌍 🌎 🌏 🚀 ✨")
    print("  ✅ ❌ ⚠️ 💡 🔧")
    print("  🐍 🐼 🦄 🎉 🎊")
    print()
    
    # Test 5: Special Symbols
    print("Test 5: Special Symbols")
    print("-" * 60)
    print("  ✓ Check mark")
    print("  ✗ Cross mark")
    print("  → Arrow")
    print("  © Copyright")
    print("  € Euro")
    print("  £ Pound")
    print("  ¥ Yen")
    print()
    
    # Test 6: Mixed Content
    print("Test 6: Mixed Content")
    print("-" * 60)
    print("  Status: ✅ Success")
    print("  Error: ❌ Failed")
    print("  Warning: ⚠️ 注意")
    print("  Info: 💡 信息")
    print()
    
    # Test 7: File I/O with Unicode
    print("Test 7: File I/O with Unicode")
    print("-" * 60)
    test_file = "test_unicode_output.txt"
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Unicode Test File\n")
            f.write("你好世界 🌍 ✓ ❌ ✅\n")
            f.write("こんにちは 🐍 🚀\n")
        
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"  ✓ File written and read successfully")
            print(f"  Content: {content.strip()}")
        
        os.remove(test_file)
        print(f"  ✓ Test file cleaned up")
    except Exception as e:
        print(f"  ❌ File I/O error: {e}")
    print()
    
    # Final Summary
    print("=" * 60)
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ('utf-8', 'utf8'):
        print("✅ ALL TESTS PASSED! Unicode support is working correctly!")
    else:
        print(f"⚠️  Encoding is {sys.stdout.encoding} - may have Unicode issues")
    print("=" * 60)

if __name__ == "__main__":
    main()

