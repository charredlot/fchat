
import random
import re
import string
import unicodedata

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)

RAND_CHARSET = string.ascii_lowercase + string.digits
def get_rand_string(length):
    return slugify(unicode(''.join( (random.choice(RAND_CHARSET) for x in range(length)) )))

