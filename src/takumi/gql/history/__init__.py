from itertools import chain

from .gig import history_items as gig_history_items

history_types = chain(gig_history_items.values())
