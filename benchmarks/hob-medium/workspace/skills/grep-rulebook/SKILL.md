---
name: grep-rulebook
description: Look up Magic: The Gathering rules in /workspace/RULEBOOK.txt using grep. Use whenever you're unsure how a keyword, timing rule, replacement effect, state-based action, or other mechanic actually works — before guessing in a card_impl.py or engine/ change.
---

`RULEBOOK.txt` (workspace root) is the Magic: The Gathering Comprehensive Rules — the authoritative source for any rules question (keyword behavior, timing, replacement vs trigger ordering, state-based actions, etc.). **Whenever you are unsure how a mechanic works, check the rulebook before guessing.** A wrong card implementation costs you a card; an incorrect-by-design helper in `engine/` can fail many cards at once.

## Read with grep, not cat / Read

`RULEBOOK.txt` is very large. Reading the whole file blows your context budget and returns mostly noise. **Always grep.** Use `Read` only to expand a specific line range you've located with grep.

## File structure (so you know what to grep for)

The file has two halves:

1. **Numbered rules** (lines ~13–3,860) — hierarchical: section (e.g. `700.`), rule (e.g. `702.2`), subrule (e.g. `702.2a`). Common sections you'll hit a lot:
   - `100.`–`199.` — game concepts (mana, damage, counters, priority)
   - `300.`–`399.` — card types (Creature, Instant, Sorcery, Enchantment, Land, Artifact, Planeswalker)
   - `500.`–`599.` — turn structure (phases, steps, untap, upkeep, combat)
   - `600.`–`699.` — spells and abilities (casting, resolving, targeting, replacement effects)
   - `701.` — keyword actions (counter, destroy, exile, sacrifice, regenerate, …)
   - `702.` — keyword abilities (flying, trample, lifelink, deathtouch, ward, …)
   - `704.` — state-based actions
2. **Glossary** (lines ~3,861 onward) — alphabetical term definitions. Often the fastest path for "what does X mean?"

## Grep recipes

```bash
# 1. Look up a keyword ability by name
#    702. is the keyword-ability section. Most keywords get one numbered subrule.
grep -n "^702\." RULEBOOK.txt | grep -i "deathtouch"
# → 3877:702.2. Deathtouch
# Then expand:
grep -n -A 20 "^702\.2\." RULEBOOK.txt | head -30

# 2. Pull a specific rule + its subrules with context
grep -n -A 30 "^704\.5\." RULEBOOK.txt        # state-based-action enumeration
grep -n -A 50 "^601\.2\." RULEBOOK.txt        # casting-a-spell steps

# 3. Glossary lookup (case-insensitive, anchored on a line that starts with the term)
#    Note: only proper keyword abilities have glossary entries. "Ability words"
#    (converge, landfall, magecraft, …) intentionally don't — they're flavor
#    tags with no rules text. If ^term returns nothing, fall through to (4).
grep -n -i "^deathtouch" RULEBOOK.txt
grep -n -i "^lifelink" RULEBOOK.txt

# 4. Find every mention of a mechanic
grep -ni "replacement effect" RULEBOOK.txt | head -20
grep -ni "ward" RULEBOOK.txt | head -20

# 5. Find which numbered rule discusses a topic, then drill in
grep -n -E "^[0-9]{3}\." RULEBOOK.txt | grep -i "combat"
# → e.g. 506. Combat Phase
grep -n -A 80 "^506\." RULEBOOK.txt
```

Once you've narrowed to a line range, switch to `Read` with `offset` + `limit` to pull just that block (cheaper than re-grepping).

## Best practices

- **Anchor with `^`** on rule-number lookups (`^702\.`, `^704\.5\.`). Without the anchor you'll match every cross-reference to those rules elsewhere in the doc.
- **Escape the dot** in rule numbers (`702\.2\.`) — grep treats `.` as any char. With BRE this matches anyway, but the explicit escape is unambiguous.
- **Start narrow, then widen.** Try the specific rule number first (`702.19` for Trample). If you don't know the number, search the glossary (`^trample`). If neither hits, search the body with `-i`.
- **Use `-A` / `-B` for context.** Rules are paragraph-shaped; `-A 20` typically captures a rule plus its first few subrules without overflowing context.
- **Cap the output with `| head -N`** on broad searches — `grep -i "creature"` returns hundreds of hits.
- **Cross-reference, don't reinvent.** Card rules text often paraphrases the rulebook; when in doubt, the numbered rule wins over your reading of the card.

## When NOT to consult the rulebook

- The behavior is already encoded in `engine/` and a working FDN reference card uses it the same way — trust the FDN example.
- The card's spec (`card_spec.json`) plus the engine source make the behavior obvious. Don't waste a grep on basic things like "does Flying restrict who can block this" (the FDN flying cards already show you).
