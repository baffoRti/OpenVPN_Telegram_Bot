import re

# Regex pattern for username validation
# Allows: letters, numbers, underscore, hyphen, dot
# Must start with a letter or number
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$')


def validate_username(username: str) -> bool:
    """
    Validate username for OpenVPN client operations.
    
    Allowed characters: letters, numbers, underscore (_), hyphen (-), dot (.)
    Must start with a letter or number.
    
    Args:
        username: The username to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not username or len(username) > 64:
        return False
    return bool(USERNAME_PATTERN.match(username))
