import random

import numpy
import xxhash


def hash_key(row, key):
    """
    Calculates a hash for a key for a specific row of the table
    The row is used as a seed in order to minimize correlations between collisions
    :return hash of the key as int
    """
    return xxhash.xxh64(str(key), seed=row).intdigest()

"""
Internal constants
"""
algorithm_basic = 0
algorithm_conservative = 1
algorithm_logcounter = 2


"""
        Initializes the Count-Min Sketch structure with the given parameters
        :param width (int) controls the number of hash buckets in one row of the table, should always be power of 2.
            The more, the better, should be very large, preferably in the same order of magnitude as the cardinality
            of the counted set.
        :param depth (int) controls the number of rows of the table. Having more rows decreases probability of a big
            overestimation. Choose a small number such as 4-8.
        :param algorithm (string) controls the algorithm used for counting
            'basic' (default)
            'conservative'
            'logcounter8'
            'logcounter1024'
        """
class CountMinSketch(object):
    """
    Data structure used to estimate frequencies of elements in massive data sets with fixed memory footprint.
    To calculate memory footprint:
        width * depth * cell_size
    Cell size is
       4B for basic algorithm
       1B for logcounter8
       2B for logcounter1024
    Example:
        width 2^26 (67 108 864), depth 4, logcounter1024 (2B) has 2^(26 + 2 + 1) = 536.8 MB
        Can be pickled to disk with this exact size

    When choosing parameters, decide on a small depth such as 4 and choose as large width as possible. Increases to width
    are far more effective than increases to depth.
    """
    def __init__(self, width=16, depth=8, algorithm=''):
        """
        Initializes the Count-Min Sketch structure with the given parameters
        :param width (int) controls the number of hash buckets in one row of the table, should always be power of 2.
            The more, the better, should be very large, preferably in the same order of magnitude as the cardinality
            of the counted set.
        :param depth (int) controls the number of rows of the table. Having more rows decreases probability of a big
            overestimation. Choose a small number such as 4-8.
        :param algorithm (string) controls the algorithm used for counting
            'basic' (default)
            'conservative'
            'logcounter8'
            'logcounter1024'
        """
        self.logshift = 0
        array_type = numpy.uint32
        self.algorithm = algorithm_basic
        self.inc_method = self.basic_increment
        if algorithm and str(algorithm).lower() == 'conservative':
            self.algorithm = algorithm_conservative
            self.inc_method = self.conservative_increment
        if algorithm and str(algorithm).lower() == 'logcounter8':
            array_type = numpy.uint8
            self.algorithm = algorithm_logcounter
            self.logshift = 2
            self.inc_method = self.log_increment
        if algorithm and str(algorithm).lower() == 'logcounter1024':
            array_type = numpy.uint16
            self.algorithm = algorithm_logcounter
            self.logshift = 9
            self.inc_method = self.log_increment

        self.width = width
        self.depth = depth
        self.hash_length = width.bit_length()
        self.hash_mask = (1 << (self.hash_length - 1)) - 1
        self.logbase = 1 << (self.logshift + 1)
        self.table = numpy.zeros((depth, width), array_type)

    def bucket(self, i, key):
        return self.hash_mask & hash_key(i, key)

    def increment(self, key):
        self.inc_method(key)

    def basic_increment(self, key):
        for row in range(self.depth):
            self.table[row][self.bucket(row, key)] += 1

    def conservative_increment(self, key):
        current = self[key]
        for row in range(self.depth):
            bucket = self.bucket(row, key)
            if self.table[row, bucket] == current:
                self.table[row, bucket] += 1

    def log_increment(self, key):
        for row in range(self.depth):
            bucket = self.bucket(row, key)
            current = int(self.table[row, bucket])
            if current < 2 * self.logbase:
                self.table[row, bucket] += 1
            else:
                mask = (1 << (current // self.logbase - 1)) - 1
                r = random.getrandbits(32)
                if (r & mask) == 0:
                    current += 1
                    self.table[row, bucket] = current

    def log_decode(self, log_value):
        if (log_value <= 2 * self.logbase):
            return log_value
        else:
            base = 1 << ((log_value >> (self.logshift + 1)) + self.logshift)
            return int(base + (log_value % self.logbase) * (base / self.logbase))

    def log_encode(self, input):
        value = int(input)
        if value <= 2 * self.logbase:
            return value
        base_bits = value.bit_length() - 1
        log_value_base = (base_bits - self.logshift) * self.logbase

        remainder = (value >> (base_bits - self.logshift - 1)) - self.logbase
        return log_value_base + remainder

    def decode(self, value):
        if self.algorithm == algorithm_logcounter:
            return self.log_decode(value)
        else:
            return value

    def __getitem__(self, key):
        minimum = min(self.table[row, self.bucket(row, key)] for row in range(self.depth))
        return self.decode(minimum)
