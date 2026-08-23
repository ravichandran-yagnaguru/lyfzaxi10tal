"""
Idiom topic bank.

Structurally distinct from topics.py (the everyday-mystery bank). These
posts use a three-beat arc -- STORY, REVEAL, USE -- instead of the five-beat
HOOK/GAP/SNAP/LIFT/GIFT arc, so they get their own bank, generator, and critic
rather than being forced into the existing schema.

ACCURACY IS A HARD GATE, NOT A SCORED AXIS
-------------------------------------------
Verifying all five idioms in the original pilot batch surfaced a real failure
rate: 2 of 5 needed correction against the popular version, and 1 of 5 had no
defensible origin at all ("let the cat out of the bag" -- multiple serious
etymology sources call the market-scam story a probable post-hoc invention).
Popular idiom folklore is not a reliable source. Every entry below has been
checked against multiple independent etymology sources, not model memory.

`verified_origin` records what's actually true. `popular_myth` records what
the post must NOT imply, even by omission -- per Guru's instruction, the post
never says "you probably think X, but actually Y." It just tells the true
story straight, the way any other post would.

SCHEMA
------
id                 stable identifier
idiom              the phrase, as commonly said
story              the true origin, written as the STORY beat (already in
                   plain, simple, funny/curious language -- see IDIOM prompt)
reveal             the REVEAL beat: the idiom landing as the punchline
use                the USE beat: a concrete modern moment to say it
verified_origin    one-line true claim, for the critic to check the draft against
popular_myth       the popular but unsupported/wrong version, if one exists.
                   Never state this in the post -- it's here so the critic can
                   catch if a draft accidentally reproduces it.
confidence         "solid" | "contested" | "unknown"
                   Only "solid" and "contested" (hedged) topics are eligible
                   to post. "unknown" topics are excluded from rotation
                   entirely -- see validate_idiom_bank().
image_style        locked engraving-prompt fragment (era, scene) -- see
                   idiom_images.py. Kept in the bank so the visual style stays
                   pinned per-idiom rather than re-improvised each time.
"""

from __future__ import annotations


IDIOM_TOPICS: list[dict] = [
    {
        "id": "bite_the_bullet",
        "idiom": "bite the bullet",
        "story": (
            "A soldier, tied down, about to be flogged. Before it starts, "
            "he's given a bullet and told to bite down -- not to numb "
            "anything, but so he can take the lashes without giving anyone "
            "the satisfaction of hearing him cry out. An officer wrote the "
            "practice down in 1785, as something soldiers already did."
        ),
        "reveal": "bite the bullet",
        "use": (
            "So when someone tells you to bite the bullet, they're describing "
            "a very old way of taking punishment silently -- not wincing, not "
            "begging, just getting through it."
        ),
        "verified_origin": (
            "First documented by Francis Grose, 1785, describing flogged "
            "soldiers biting a bullet to avoid crying out. No credible "
            "evidence ties the phrase to battlefield surgery."
        ),
        "popular_myth": (
            "Widely believed to originate in pre-anesthesia battlefield "
            "amputations. Timeline doesn't work -- ether/chloroform predate "
            "the Civil War and the phrase's first print use (Kipling, 1891)."
        ),
        "confidence": "solid",
        "image_style": (
            "18th-century naval deck, a bound man biting down on an object "
            "clenched in his teeth, an officer with a whip standing before "
            "him, sailors watching, tall ship rigging and a flag behind them"
        ),
    },
    {
        "id": "break_the_ice",
        "idiom": "break the ice",
        "story": (
            "A river, frozen solid, and a boat that needs to get through "
            "before the ice thickens further. Someone has to go first -- walk "
            "out onto the ice and crack a path with a pole, so the boat "
            "behind them has somewhere to move. It's slow, it's cold, and "
            "nobody wants the job."
        ),
        "reveal": "break the ice",
        "use": (
            "So when you break the ice at a party, you're doing exactly what "
            "that person on the river did: going first, so everyone behind "
            "you has somewhere to go."
        ),
        "verified_origin": (
            "Figurative use recorded by Erasmus in Latin (Adagia, 1528, "
            "crediting Francesco Filelfo) and in Shakespeare's Taming of the "
            "Shrew (c. 1590) -- both predate purpose-built polar icebreaker "
            "ships by centuries. Root image is a small river crossing, not "
            "an Arctic vessel."
        ),
        "popular_myth": (
            "Commonly attributed to 19th-century Arctic icebreaker ships. "
            "Chronologically backwards -- the figurative phrase is far older "
            "than that ship type."
        ),
        "confidence": "solid",
        "image_style": (
            "19th-century frozen river scene, a man with a long pole cracking "
            "a path through river ice, small boats waiting behind him, "
            "period clothing, riverside town in the distance"
        ),
    },
    {
        "id": "caught_red_handed",
        "idiom": "caught red-handed",
        "story": (
            "Scotland, the 1400s. A man is found standing over a poached "
            "deer, blood still on his hands. Under the law at the time, that "
            "was the proof. Not a witness, not a confession -- just the "
            "hands themselves, red, at the scene. Courts wrote it down "
            "exactly like that: taken with the red hand."
        ),
        "reveal": "caught red-handed",
        "use": (
            "So when someone's caught red-handed today, there's no blood and "
            "usually no deer, but the logic is identical to a 500-year-old "
            "courtroom: caught with the evidence still on them."
        ),
        "verified_origin": (
            "Documented in the Scottish Acts of Parliament of James I, 1432, "
            "as 'reid hand' -- someone caught with blood on their hands as "
            "legal proof of poaching or murder. Popularised in modern "
            "'red-handed' form by Walter Scott's Ivanhoe, 1819."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "image_style": (
            "15th-century Scottish courtroom, a man standing before seated "
            "magistrates in a torch-lit stone hall, one magistrate pointing "
            "at him, period dress, arched stone architecture"
        ),
    },
]


def get_idiom(idiom_id: str) -> dict | None:
    return next((t for t in IDIOM_TOPICS if t["id"] == idiom_id), None)


def validate_idiom_bank() -> list[str]:
    """
    Self-check. Run at startup, same pattern as topics.validate_bank().

    Hard rule: no "unknown"-confidence idiom may ship. If verification later
    downgrades an idiom's confidence to "unknown" (new research undermines
    the story), it must be pulled from rotation, not just flagged.
    """
    problems: list[str] = []
    seen: set[str] = set()
    required = ("id", "idiom", "story", "reveal", "use", "verified_origin", "confidence", "image_style")
    valid_confidence = {"solid", "contested", "unknown"}

    for t in IDIOM_TOPICS:
        tid = t.get("id", "<missing id>")
        for field in required:
            if not t.get(field):
                problems.append(f"{tid}: missing required field '{field}'")
        if tid in seen:
            problems.append(f"{tid}: duplicate id")
        seen.add(tid)

        if t.get("confidence") not in valid_confidence:
            problems.append(f"{tid}: invalid confidence {t.get('confidence')!r}")
        if t.get("confidence") == "unknown":
            problems.append(
                f"{tid}: confidence is 'unknown' -- must be excluded from rotation, "
                "not merely flagged. Remove from IDIOM_TOPICS or upgrade the verification."
            )

    return problems


if __name__ == "__main__":
    issues = validate_idiom_bank()
    print(f"{len(IDIOM_TOPICS)} idioms, confidence: "
          f"{[(t['id'], t['confidence']) for t in IDIOM_TOPICS]}")
    if issues:
        print("PROBLEMS:")
        for p in issues:
            print("  -", p)
    else:
        print("Bank OK.")
