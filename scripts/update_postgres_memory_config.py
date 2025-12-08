#!/usr/bin/env python3
"""Update docker-compose.yml with dynamic PostgreSQL memory configuration"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.memory_config import (
    generate_docker_compose_postgres_command,
    get_memory_status,
    logger,
)


def update_docker_compose():
    """Update docker-compose.yml with dynamic memory configuration"""
    docker_compose_path = project_root / "docker-compose.yml"
    
    if not docker_compose_path.exists():
        logger.error(f"docker-compose.yml not found at {docker_compose_path}")
        return False
    
    # Read current file
    with open(docker_compose_path, "r") as f:
        content = f.read()
    
    # Generate new command
    new_command = generate_docker_compose_postgres_command()
    
    # Check if command section exists
    if "command:" in content:
        # Replace existing command
        import re
        
        # Match command: > or command: | followed by postgres settings
        pattern = r"command:\s*[>|]\s*(?:postgres.*?)(?=\n\s*[a-z]|\n\s*volumes:|\Z)"
        replacement = f"command: >\n      {new_command}"
        
        if re.search(pattern, content, re.DOTALL | re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.DOTALL | re.MULTILINE)
            logger.info("Updated existing command in docker-compose.yml")
        else:
            # Add command after environment section
            env_pattern = r"(environment:\s*\n(?:\s+[A-Z_]+:.*\n)+)"
            replacement = f"\\1    command: >\n      {new_command}\n"
            content = re.sub(env_pattern, replacement, content)
            logger.info("Added command to docker-compose.yml")
    else:
        # Add command section after environment
        env_pattern = r"(environment:\s*\n(?:\s+[A-Z_]+:.*\n)+)"
        replacement = f"\\1    command: >\n      {new_command}\n"
        content = re.sub(env_pattern, replacement, content)
        logger.info("Added command section to docker-compose.yml")
    
    # Write updated file
    with open(docker_compose_path, "w") as f:
        f.write(content)
    
    logger.info(f"Updated {docker_compose_path} with dynamic memory configuration")
    return True


def main():
    """Main function"""
    print("PostgreSQL Dynamic Memory Configuration")
    print("=" * 50)
    
    # Show current status
    status = get_memory_status()
    print(f"\nSystem Memory:")
    print(f"  Total: {status['total_memory_mb']:.0f} MB")
    print(f"  Available: {status['available_memory_mb']:.0f} MB")
    print(f"  Target ({status['memory_percent']}%): {status['target_memory_mb']:.0f} MB")
    
    print(f"\nPostgreSQL Configuration:")
    for key, value in status['postgres_config'].items():
        print(f"  {key}: {value}")
    
    if status['is_windows']:
        print(f"\n[WARNING] Windows detected - maintenance_work_mem limited to avoid shared memory errors")
    
    print(f"\nGenerated command:")
    command = generate_docker_compose_postgres_command()
    print(f"  {command}")
    
    # Update docker-compose.yml
    print(f"\nUpdating docker-compose.yml...")
    if update_docker_compose():
        print("[SUCCESS] Successfully updated docker-compose.yml")
        print("\n[NOTE] Restart PostgreSQL container for changes to take effect:")
        print("   docker-compose restart postgres")
    else:
        print("[ERROR] Failed to update docker-compose.yml")
        sys.exit(1)


if __name__ == "__main__":
    main()

