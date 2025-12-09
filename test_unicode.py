#!/usr/bin/env python3
"""Test script to verify Unicode/UTF-8 encoding works correctly

This script tests various Unicode characters and emojis to ensure
the workspace-level encoding solution is working properly.
"""

import sys
import subprocess
import os

def test_direct_print():
    """Test direct printing of Unicode characters"""
    print("=" * 60)
    print("TEST 1: Direct Print with Unicode Characters")
    print("=" * 60)
    
    # Test various Unicode characters and emojis
    test_strings = [
        "✓ Checkmark",
        "❌ Cross mark",
        "✅ Check mark button",
        "🌟 Star",
        "🚀 Rocket",
        "💡 Light bulb",
        "🎉 Party popper",
        "🔥 Fire",
        "❤️ Heart",
        "👍 Thumbs up",
        "你好世界 - Chinese: Hello World",
        "こんにちは - Japanese: Hello",
        "Здравствуй - Russian: Hello",
        "مرحبا - Arabic: Hello",
        "🌍 Earth globe",
        "🎯 Direct hit",
        "⚡ Lightning",
        "🎨 Artist palette",
        "📊 Bar chart",
        "🔒 Locked",
    ]
    
    for test_str in test_strings:
        print(f"  {test_str}")
    
    print("\n✅ Direct print test completed successfully!")
    return True

def test_encoding_info():
    """Test and display encoding information"""
    print("\n" + "=" * 60)
    print("TEST 2: Encoding Information")
    print("=" * 60)
    
    print(f"  sys.stdout.encoding: {sys.stdout.encoding}")
    print(f"  sys.stderr.encoding: {sys.stderr.encoding}")
    print(f"  sys.stdin.encoding: {sys.stdin.encoding}")
    print(f"  sys.getdefaultencoding(): {sys.getdefaultencoding()}")
    print(f"  PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'not set')}")
    print(f"  PYTHONUTF8: {os.environ.get('PYTHONUTF8', 'not set')}")
    
    # Check if encoding is UTF-8
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ('utf-8', 'utf8'):
        print("\n  ✅ Encoding is UTF-8 - Unicode support enabled!")
        return True
    else:
        print(f"\n  ⚠️  Encoding is {sys.stdout.encoding} - may have Unicode issues")
        return False

def test_subprocess():
    """Test subprocess with Unicode characters"""
    print("\n" + "=" * 60)
    print("TEST 3: Subprocess with Unicode")
    print("=" * 60)
    
    # Test subprocess call with Unicode
    test_code = """
import sys
print('✓ Subprocess Unicode test')
print('❌ Cross mark')
print('✅ Success')
print('🌟 Star emoji')
print('你好世界')
print(f'Encoding: {sys.stdout.encoding}')
"""
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", test_code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=os.environ.copy(),
        )
        
        print("Subprocess output:")
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Subprocess test completed successfully!")
            return True
        else:
            print(f"❌ Subprocess test failed with return code: {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Subprocess test failed with exception: {e}")
        return False

def test_file_io():
    """Test file I/O with Unicode"""
    print("\n" + "=" * 60)
    print("TEST 4: File I/O with Unicode")
    print("=" * 60)
    
    test_file = "test_unicode_output.txt"
    test_content = "✓ ❌ ✅ 🌟 🚀 💡 🎉 🔥 ❤️ 👍 你好世界 🌍 🎯 ⚡ 🎨 📊 🔒\n"
    
    try:
        # Write Unicode to file
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        # Read Unicode from file
        with open(test_file, "r", encoding="utf-8") as f:
            read_content = f.read()
        
        if read_content == test_content:
            print(f"  ✅ File I/O test passed!")
            print(f"  Content: {read_content.strip()}")
            # Clean up
            os.remove(test_file)
            return True
        else:
            print(f"  ❌ File I/O test failed - content mismatch")
            return False
    except Exception as e:
        print(f"  ❌ File I/O test failed with exception: {e}")
        return False

def main():
    """Run all Unicode tests"""
    print("\n" + "=" * 60)
    print("UNICODE/UTF-8 ENCODING TEST SUITE")
    print("=" * 60)
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()
    
    results = []
    
    # Run all tests
    results.append(("Direct Print", test_direct_print()))
    results.append(("Encoding Info", test_encoding_info()))
    results.append(("Subprocess", test_subprocess()))
    results.append(("File I/O", test_file_io()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Unicode support is working correctly!")
        print("=" * 60)
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - Check encoding configuration")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())

