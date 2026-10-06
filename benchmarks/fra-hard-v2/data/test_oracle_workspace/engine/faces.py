"""Multi-face cards whose faces are separate objects (CR 715; see ADR-017).

A card with more than one face lists them through ``faces()``: the card itself
for its main face, then one object for each other face, whose ``whole_card`` is
the card. Only the card sits in a zone; a face object stands for the card while
that face is cast and on the stack, and the card takes its place again when the
spell leaves the stack (CR 715.3b, 715.4).

How a query presents such a card is this engine's choice: each face as its own
option, or the card and then, once it is chosen, a question naming the face to
cast. :data:`PRESENT_EACH_FACE` selects the first; the portability tests switch
it off to show that every audited suite passes under either.
"""

from __future__ import annotations

from typing import Any, Callable

PRESENT_EACH_FACE = True


def faces_of(card: Any) -> list[Any]:
    """*card*'s faces, main face first; a single-faced card is its only face."""
    faces = getattr(card, "faces", None)
    return list(faces()) if callable(faces) else [card]


def whole_card(obj: Any) -> Any:
    """The card *obj* is a face of, or *obj* itself."""
    return getattr(obj, "whole_card", None) or obj


def is_adventure(obj: Any) -> bool:
    return whole_card(obj) is not obj and "Adventure" in getattr(obj, "subtypes", ())


def presented(cards: list[Any], keep: Callable[[Any], bool] = lambda face: True) -> list[Any]:
    """The objects a query presents for *cards*: their faces that *keep* allows,
    one option each, or each card with any such face."""
    objects = []
    for card in cards:
        faces = [face for face in faces_of(card) if keep(face)]
        if PRESENT_EACH_FACE:
            objects.extend(faces)
        elif faces:
            objects.append(card)
    return objects


def choose_face(
    game: Any, player: Any, chosen: Any, keep: Callable[[Any], bool] = lambda face: True
) -> Any:
    """The face to cast for *chosen*, an object :func:`presented` offered.

    A presented face is cast as it is; a presented card whose faces *keep*
    allows more than one is followed by a question naming the face.
    """
    if chosen is None or whole_card(chosen) is not chosen:
        return chosen
    faces = [face for face in faces_of(chosen) if keep(face)]
    if len(faces) <= 1:
        return faces[0] if faces else chosen
    from engine.card_queries import choose_object

    return choose_object(game, player, faces, "Choose the face to cast", source_card=chosen)


def cast_offers(
    game: Any, player: Any, card: Any, faces: list[Any], cast: Callable[[Any], Any]
) -> list[tuple[Any, Callable[[], Any]]]:
    """Priority Query offers for casting *card* as one of *faces* through *cast*."""
    if not faces:
        return []
    if PRESENT_EACH_FACE:
        return [(face, lambda face=face: cast(face)) for face in faces]
    allowed = {id(face) for face in faces}
    return [(card, lambda: cast(choose_face(game, player, card, lambda f: id(f) in allowed)))]
