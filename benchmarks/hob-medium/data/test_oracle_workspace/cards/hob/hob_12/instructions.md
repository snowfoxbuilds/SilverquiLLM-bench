# The Eagles Are Coming!

Implement the printed kicker as an optional additional cost, selected before choosing targets. The kicked total is {3}{W}{W}{W}; a free cast still pays the kicker. Without kicker exactly one target is required. With kicker zero or more distinct targets are legal.

Targets are creatures you own, including ones an opponent controls. A creature you control but do not own is not eligible. Recheck creature type, ownership, protection and the original zone stint when resolving; a creature that left and returned is a new object.

Count only creatures actually returned to your hand. Tokens count if they reached the hand, even though state-based actions subsequently remove them. Retain the count independently of the spell, and create that many 4/4 white Bird Soldier tokens with flying at the next upkeep, whichever player owns that turn. The delayed trigger fires once. A token's color must be represented independently of its zero mana cost.

Use the Player Query / Player Decision protocol for the optional kicker payment and targets. BOOL yes/no decisions express the kicker choice. Target references identify the actual objects, not positions in a mutable battlefield list.
