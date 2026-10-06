# FRA hard implementation task

Implement the eleven selected cards listed in the card specs under cards/fra/, cards/hob/, cards/war/ and cards/fut/. Keep each card's implementation in its assigned card_impl.py, and keep the predefined classes its stub declares under their names. card_spec.json contains the complete card specification, including card_faces for cards with multiple components. Implement the whole card.

You may change engine/ freely. Use the Player Query / Player Decision protocol for every choice: the engine offers each player, at priority, the choices a real player could make, and every option carries the predefined class it stands for in its `printed` attr. An illegal choice is rejected with InvalidPlayerChoiceError. Your tests belong beside target implementations. Run `python3 -m pytest` from the workspace root. Consult RULEBOOK.txt for rules and test_utils.md for test APIs.
