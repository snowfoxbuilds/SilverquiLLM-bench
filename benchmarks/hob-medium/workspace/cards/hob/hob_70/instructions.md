# Gollum, Riddle Master

The odd/even choice happens as this permanent enters, before its enters-the-battlefield event, and repeats whenever it leaves and reenters. Zero is even. A spell with X in its cost uses the chosen X while it is on the stack; reducing or replacing its mana payment does not change that mana value.

Watch opponents' casts, not resolutions and not spell copies. Choose an unused mode when placing the triggered ability on the stack. Reserve that mode then so two pending triggers cannot select it twice. If every mode has been chosen, there is no legal mode to put on the stack. Mode memory belongs to this battlefield stint and resets on reentry, not at turn boundaries.

A counter mode cannot put a counter on a new incarnation of Gollum. Draw and drain modes still resolve after the source leaves. Drain makes each opponent lose 2 life but gains its controller 2 life total. Use the engine's gain_life/lose_life functions.

Use MODE decisions with names odd/even for the entry choice and counter/drain/draw for the three printed modes, in printed order. These are the benchmark's public choice labels; do not inspect query text in tests or bypass the Player Query protocol.
