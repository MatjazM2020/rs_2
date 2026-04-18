#!/usr/bin/env python3
"""
Fallback MESI Two Level Cache Hierarchy
Uses classic cache hierarchy if Ruby MESI protocol is not available.
"""

import sys
import os

# First try to use Ruby MESI if available
try:
    from mesi_two_level import MESITwoLevelCacheHierarchy
    USING_RUBY = True
except Exception as e:
    USING_RUBY = False
    print(f"Ruby MESI not available, using fallback classic cache. Error was: {e}", file=sys.stderr)
    
    # Fall back to classic cache hierarchy
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'smp_classic'))
    from three_level import PrivateL1PrivateL2SharedL3CacheHierarchy
    
    # Create an alias for compatibility
    class MESITwoLevelCacheHierarchy(PrivateL1PrivateL2SharedL3CacheHierarchy):
        """Wrapper that uses classic cache hierarchy as fallback for MESI"""
        
        def __init__(self, l1i_size="32KiB", l1i_assoc=8, l1d_size="32KiB", 
                     l1d_assoc=8, l2_size="256KiB", l2_assoc=8, num_l2_banks=1):
            # Map MESI parameters to classic cache hierarchy parameters
            super().__init__(
                l1d_size=l1d_size,
                l1i_size=l1i_size,
                l2_size=l2_size,
                l3_size="8MiB",  # Shared L3
                l1d_assoc=l1d_assoc,
                l1i_assoc=l1i_assoc,
                l2_assoc=l2_assoc,
                l3_assoc=16
            )

__all__ = ['MESITwoLevelCacheHierarchy', 'USING_RUBY']
