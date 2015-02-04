import base64
import random
import hashlib

def generateKey():
    """Create a random API key."""
    
    entropy = str(random.getrandbits(256))
    hashed = hashlib.sha256(entropy).digest()
    bits = random.choice(['rA','aZ','gQ','hH','hG','aR','DD'])
    
    return base64.b64encode(hashed, bits).rstrip('==')

if __name__ == '__main__':
    newKey = generateKey()
    
    with open("local-api-key.txt", "w") as f:
        f.writelines(newKey)
    f.closed
    
    print("Generated new API key for app: {}".format(newKey))
        