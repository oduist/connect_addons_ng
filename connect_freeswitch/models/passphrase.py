"""Human-readable passphrase generator for SIP endpoint credentials.

Format: five lowercase words, each followed by a single digit, joined by
hyphens, e.g. ``flour3-tower9-rome1-watching2-hello8``. The combination of a
curated wordlist (~240 words) and per-word digits yields high entropy
(~54 bits for the default five words) while staying easy to read aloud and
type into a softphone or SIP desk phone keypad.

The generator uses :mod:`secrets` (CSPRNG), never :mod:`random`, because the
output is a security credential.
"""
import secrets

# Short, neutral, easy-to-spell English words (3-7 letters). Curated to avoid
# ambiguous look-alikes and anything offensive. Order is irrelevant.
WORDS = [
    # animals
    'ant', 'bat', 'bear', 'bee', 'bird', 'bison', 'bull', 'calf', 'camel',
    'cat', 'clam', 'cobra', 'colt', 'cow', 'crab', 'crane', 'crow', 'deer',
    'dog', 'dove', 'duck', 'eagle', 'eel', 'elk', 'emu', 'fawn', 'finch',
    'fish', 'fox', 'frog', 'gecko', 'goat', 'goose', 'hare', 'hawk', 'hen',
    'heron', 'horse', 'ibis', 'jay', 'koala', 'lamb', 'lark', 'lion', 'llama',
    'lynx', 'mole', 'moose', 'moth', 'mouse', 'mule', 'newt', 'owl', 'panda',
    'pig', 'pony', 'puma', 'quail', 'rabbit', 'ram', 'rat', 'raven', 'robin',
    'seal', 'shark', 'sheep', 'skunk', 'sloth', 'snail', 'snake', 'sparrow',
    'squid', 'stork', 'swan', 'tiger', 'toad', 'trout', 'tuna', 'turkey',
    'viper', 'wasp', 'whale', 'wolf', 'wren', 'yak', 'zebra',
    # nature
    'bay', 'beach', 'bloom', 'breeze', 'brook', 'cave', 'cliff', 'cloud',
    'coast', 'coral', 'creek', 'dawn', 'delta', 'dune', 'dusk', 'earth',
    'fern', 'field', 'flame', 'flower', 'forest', 'frost', 'glade', 'grove',
    'hill', 'isle', 'lake', 'leaf', 'marsh', 'meadow', 'mist', 'moon', 'moss',
    'ocean', 'peak', 'petal', 'pine', 'plain', 'pond', 'rain', 'reef', 'ridge',
    'river', 'rock', 'root', 'sand', 'snow', 'star', 'stone', 'storm',
    'stream', 'sun', 'thorn', 'tide', 'tree', 'valley', 'vine', 'wave', 'wind',
    'wood',
    # food
    'apple', 'bacon', 'bagel', 'bean', 'berry', 'bread', 'broth', 'butter',
    'cake', 'candy', 'carrot', 'cherry', 'chili', 'cocoa', 'corn', 'cream',
    'crust', 'curry', 'dough', 'fig', 'flour', 'grain', 'grape', 'gravy',
    'herb', 'honey', 'jam', 'kale', 'lemon', 'lime', 'mango', 'maple', 'melon',
    'milk', 'mint', 'oat', 'olive', 'onion', 'orange', 'peach', 'pear',
    'pecan', 'pepper', 'pie', 'plum', 'rice', 'sauce', 'soup', 'spice',
    'sugar', 'syrup', 'taco', 'toast', 'wheat',
    # objects
    'anchor', 'arrow', 'badge', 'basket', 'bell', 'boat', 'book', 'bottle',
    'bowl', 'brick', 'bridge', 'broom', 'brush', 'bucket', 'candle', 'cart',
    'chain', 'chair', 'clock', 'coin', 'comb', 'cup', 'desk', 'dish', 'door',
    'drum', 'flag', 'fork', 'frame', 'gate', 'glove', 'hammer', 'hat', 'hook',
    'jar', 'kettle', 'key', 'knife', 'ladder', 'lamp', 'lantern', 'lock',
    'map', 'marble', 'mirror', 'nail', 'net', 'oar', 'paddle', 'pencil',
    'pillow', 'plate', 'pot', 'quilt', 'ribbon', 'ring', 'rope', 'ruler',
    'saddle', 'sail', 'scarf', 'shell', 'shovel', 'spoon', 'stamp', 'table',
    'thread', 'ticket', 'torch', 'towel', 'vase', 'wagon', 'wheel', 'whistle',
]

DIGITS = '0123456789'


def generate_passphrase(word_count=5):
    """Return a passphrase of ``word_count`` ``word+digit`` groups joined by '-'.

    Example: ``flour3-tower9-rome1-watching2-hello8``.
    """
    return '-'.join(
        '{}{}'.format(secrets.choice(WORDS), secrets.choice(DIGITS))
        for _ in range(word_count)
    )
