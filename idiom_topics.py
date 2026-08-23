"""
Idiom topic bank -- v2.

Structurally distinct from topics.py (the everyday-mystery bank). These
posts use a three-beat arc -- STORY, REVEAL, USE -- instead of the five-beat
HOOK/GAP/SNAP/LIFT/GIFT arc, so they get their own bank, generator, and critic
rather than being forced into the existing schema.

ACCURACY IS A HARD GATE, NOT A SCORED AXIS
-------------------------------------------
Verifying the original pilot batch surfaced a real failure rate: popular
idiom folklore is not a reliable source (2 of 5 pilot idioms needed
correction against the popular version). Every entry below was checked
against etymology sources (phrases.org.uk, worldwidewords.org, etymonline,
OED-citing references, Snopes for the myth-busting), not model memory alone.

THE THREE CONFIDENCE TIERS (v2 change)
--------------------------------------
v1 excluded idioms whose origin couldn't be documented. Per Guru's
direction, that was the wrong rule: an undocumented origin isn't a reason
to drop the idiom -- it's a different kind of story, and the honest move is
to SAY it's a story. So:

  solid      documented origin. Told straight, as fact.
  contested  real evidence exists but the link is unproven or accounts
             compete. The uncertain part must be hedged naturally
             ("the earliest record we have...", "the story most people
             point to...").
  folklore   no documented origin. The popular story may be told ONLY as
             a story passed down -- "the story people tell...", "as the
             grapevine has it...", "nobody can prove it, but..." -- and
             the post should own that honestly. What IS documented (first
             appearance in print, what the theories are) goes in
             verified_origin so the critic can hold the line.

Nothing is excluded from rotation any more. The accuracy gate's job shifts
per tier: for solid, no contradiction or invention; for contested, no
stating the unproven part as flat fact; for folklore, no presenting the
legend as documented history.

`popular_myth` records the widespread-but-wrong (or unprovable) version.
For solid/contested entries the post must never present it as the origin.
For folklore entries it IS the passed-down story, and may be retold only
with clear grapevine framing. Never frame any post as a correction of the
reader ("you probably think...") -- that rule is unchanged.

SCHEMA
------
id                 stable identifier
idiom              the phrase, as commonly said
story              the true origin (or, folklore tier: the honest framing of
                   the legend), written as target content for the STORY beat
reveal             the REVEAL beat: the idiom landing as the punchline
use                the USE beat: a concrete modern moment to say it
verified_origin    what is actually documented, for the critic to check
                   the draft against
popular_myth       the popular but unsupported/wrong version, if one exists
confidence         "solid" | "contested" | "folklore"
era                century label for the engraving image prompt ("18th" etc.)
image_style        locked engraving-prompt scene -- see idiom_images.py
"""

from __future__ import annotations


IDIOM_TOPICS: list[dict] = [
    # ------------------------------------------------------------ pilot 3
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
        "era": "18th",
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
            "out onto the ice and crack a path, so the boat behind them has "
            "somewhere to move. It's slow, it's cold, and nobody wants the job."
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
        "era": "19th",
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
        "era": "15th",
        "image_style": (
            "15th-century Scottish courtroom, a man standing before seated "
            "magistrates in a torch-lit stone hall, one magistrate pointing "
            "at him, period dress, arched stone architecture"
        ),
    },

    # ------------------------------------------------- solid, documented
    {
        "id": "read_the_riot_act",
        "idiom": "read someone the riot act",
        "story": (
            "England, 1715. A crowd of twelve or more gets rowdy, and a "
            "magistrate climbs the steps, unrolls a paper, and reads a real "
            "proclamation aloud, beginning 'Our Sovereign Lord the King "
            "chargeth and commandeth...'. From that moment the crowd has one "
            "hour to scatter. Staying past the hour was a capital crime. The "
            "reading wasn't a telling-off -- it was a countdown."
        ),
        "reveal": "reading them the riot act",
        "use": (
            "Now it's what a parent does when the living room becomes a "
            "wrestling ring -- a final warning, delivered with authority, "
            "clock officially running."
        ),
        "verified_origin": (
            "The Riot Act, passed by the British Parliament in 1714 and in "
            "force from 1715: an official could order any crowd of twelve or "
            "more to disperse by reading a set proclamation aloud; refusing "
            "to leave within an hour was punishable by death. Figurative use "
            "for a stern warning recorded by 1819."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "18th",
        "image_style": (
            "18th-century English town square, an official in a tricorn hat "
            "standing on stone steps reading aloud from an unrolled paper, "
            "an unruly crowd gathered below, timber-framed buildings behind"
        ),
    },
    {
        "id": "steal_thunder",
        "idiom": "steal someone's thunder",
        "story": (
            "London, 1709. A struggling playwright named John Dennis invents "
            "a new backstage machine that makes convincing thunder for his "
            "play at Drury Lane. The play flops and closes. Weeks later he "
            "sits in the same theatre watching Macbeth -- and hears HIS "
            "thunder roll across the stage. He reportedly stood up and "
            "raged that they wouldn't run his play, but they'd happily run "
            "his thunder."
        ),
        "reveal": "stealing his thunder",
        "use": (
            "It's what happens when you rehearse your big announcement for "
            "a week, and someone else casually drops the same news at the "
            "start of the meeting."
        ),
        "verified_origin": (
            "Documented theatre history: playwright John Dennis devised a "
            "new thunder effect for his play Appius and Virginia at Drury "
            "Lane (usually dated 1709; some sources say 1704). After the "
            "play closed, the effect was used in a production of Macbeth "
            "and Dennis's furious complaint was recorded by Joseph Spence. "
            "His exact words are disputed between accounts."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "18th",
        "image_style": (
            "18th-century theatre backstage, a man cranking a wooden thunder "
            "machine with metal balls in a trough, the lit stage and "
            "audience visible beyond the curtain edge"
        ),
    },
    {
        "id": "crocodile_tears",
        "idiom": "crocodile tears",
        "story": (
            "Medieval Europe's animal books -- bestiaries -- taught that the "
            "crocodile weeps while it eats its prey. A famous 14th-century "
            "travel book spread it wide: 'these serpents slay men, and they "
            "eat them weeping.' Preachers loved it as a picture of fake "
            "repentance, and by 1563 an English archbishop was using "
            "'crocodile tears' for counterfeit sorrow. The odd footnote: "
            "crocodiles really do tear up while feeding -- it's just "
            "lubrication, not grief."
        ),
        "reveal": "crocodile tears",
        "use": (
            "It's the colleague who sobs about your missed promotion and "
            "then applies for the same post that afternoon."
        ),
        "verified_origin": (
            "The weeping-crocodile legend appears in ancient proverbs "
            "attributed to Plutarch and in medieval bestiaries; Sir John "
            "Mandeville's popular 14th-century travel book spread it in "
            "English ('they eat them weeping'); the phrase 'crocodile "
            "tears' is recorded in English by 1563 (Edmund Grindal). Real "
            "crocodiles do produce tears while feeding, for lubrication, "
            "not emotion."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "15th",
        "image_style": (
            "medieval bestiary style scene, a large crocodile on a river "
            "bank with visible tear drops, a wary traveler in period dress "
            "watching from behind reeds"
        ),
    },
    {
        "id": "bury_the_hatchet",
        "idiom": "bury the hatchet",
        "story": (
            "Long before European settlers arrived, the nations of the "
            "Iroquois Confederacy sealed peace in a way you could see: "
            "weapons were ceremonially buried, put into the earth so the "
            "conflict was literally underground. French records from 1644 "
            "describe Iroquois envoys speaking of hurling the hatchet so "
            "deep into the earth it would never be seen again. Settlers "
            "borrowed the image, and English has kept it ever since."
        ),
        "reveal": "bury the hatchet",
        "use": (
            "So when two cousins finally bury the hatchet after years of "
            "not talking, they're echoing a real diplomatic ceremony, not "
            "just a figure of speech."
        ),
        "verified_origin": (
            "Documented Iroquois practice of ceremonially burying weapons "
            "at peacemaking, tied to the founding tradition of the Iroquois "
            "Confederacy; French colonial records from 1644 describe the "
            "custom, and the English idiom appears in America in the 17th "
            "century."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "17th",
        "image_style": (
            "17th-century forest clearing, men gathered in a circle "
            "watching a hatchet being placed into the ground beneath a "
            "tall pine tree, dignified ceremonial scene"
        ),
    },
    {
        "id": "deadline",
        "idiom": "deadline",
        "story": (
            "1864, Andersonville prison camp, Georgia. About twenty feet "
            "inside the stockade wall runs a low wooden rail. The rule, "
            "recorded in the camp's own inspection reports, is brutally "
            "simple: any prisoner who crosses that line is shot without "
            "warning. The guards called it the dead line. The word survived "
            "the war, drifted into printing shops and newsrooms, and went "
            "soft -- the only thing it kills now is your evening."
        ),
        "reveal": "deadline",
        "use": (
            "Worth remembering at 11:58pm as you hit submit: the original "
            "deadline was a line on the ground, and 'don't cross it' was "
            "meant exactly."
        ),
        "verified_origin": (
            "Documented in Confederate inspection reports of Andersonville "
            "prison (Walter Bowie, May 1864; D.T. Chandler, July 1864) and "
            "in the postwar trial of camp commandant Henry Wirz: a line "
            "about twenty feet inside the stockade that prisoners were "
            "forbidden to cross on pain of being shot. The modern 'time "
            "limit' sense grew later, via printing and journalism."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "19th",
        "image_style": (
            "19th-century wooden prison stockade wall with a low wooden "
            "rail running parallel inside it, guards silhouetted on the "
            "parapet, tents in the background, somber scene, no violence"
        ),
    },
    {
        "id": "saved_by_the_bell",
        "idiom": "saved by the bell",
        "story": (
            "A boxing ring in the 1890s. A fighter goes down. The referee "
            "counts -- seven, eight, nine -- and before ten can land, the "
            "bell clangs to end the round. The count dies with it. The "
            "fighter gets dragged to his corner, doused, revived, and "
            "granted a whole new round he had no right to expect. "
            "Sportswriters had a phrase for that rescue by 1893."
        ),
        "reveal": "saved by the bell",
        "use": (
            "It's the teacher asking who wants to solve the problem on the "
            "board -- and the period bell ringing before your name comes up."
        ),
        "verified_origin": (
            "Boxing slang from the late 19th century: a floored boxer being "
            "counted out is spared when the end-of-round bell rings first. "
            "Earliest print reference: The Fitchburg Daily Sentinel, "
            "Massachusetts, February 1893."
        ),
        "popular_myth": (
            "Widely claimed to come from 'safety coffins' fitted with bells "
            "for people buried alive. No evidence supports this as the "
            "origin -- the phrase doesn't appear in that context and is "
            "documented boxing slang."
        ),
        "confidence": "solid",
        "era": "19th",
        "image_style": (
            "19th-century boxing ring, a fallen boxer on one knee, a "
            "referee mid-count with raised fingers, a man at ringside "
            "striking a bell, crowd in period dress leaning in"
        ),
    },
    {
        "id": "red_herring",
        "idiom": "red herring",
        "story": (
            "1807. English journalist William Cobbett is furious that the "
            "newspapers have trumpeted a false report of Napoleon's defeat. "
            "So he prints a little story from his boyhood: how he once "
            "dragged a strong-smelling smoked herring -- reddish-brown from "
            "the smokehouse -- across a trail to pull hounds off a hare's "
            "scent. The confession that makes it delicious: he apparently "
            "invented the anecdote. A made-up story about misleading "
            "hounds, used to accuse the press of misleading the public, "
            "became the permanent name for misleading anyone."
        ),
        "reveal": "a red herring",
        "use": (
            "It's every detective show that spends twenty minutes making "
            "you suspect the gardener."
        ),
        "verified_origin": (
            "Figurative use traced to William Cobbett's article of 14 "
            "February 1807, using a (likely fictional) tale of dragging a "
            "smoked herring across a trail to distract hounds, aimed at "
            "newspapers that had falsely reported Napoleon's defeat. Per "
            "etymologist Michael Quinion (accepted by the OED), it did not "
            "come from a real hunting practice. There is no fish species "
            "called a red herring -- it's herring cured red by heavy smoking."
        ),
        "popular_myth": (
            "Often said to come from actually training hunting hounds with "
            "smoked herrings. The practice is unevidenced; the idiom comes "
            "from Cobbett's rhetorical story about it."
        ),
        "confidence": "solid",
        "era": "19th",
        "image_style": (
            "19th-century English country lane, a man dragging a fish on a "
            "string across the path, a pack of hounds veering off a trail "
            "toward the scent, hedgerows and fields behind"
        ),
    },
    {
        "id": "cold_shoulder",
        "idiom": "the cold shoulder",
        "story": (
            "1816. Walter Scott, writing The Antiquary, has a character "
            "notice a countess's displeasure -- shown, in Scots, by the "
            "'cauld shouther'. Not a plate of anything. A shoulder: turned, "
            "hunched, angled away, the body saying what the mouth won't. "
            "Scott used it again years later, England picked it up, and the "
            "gesture became the idiom."
        ),
        "reveal": "the cold shoulder",
        "use": (
            "You've seen it this week: the colleague who answers everyone "
            "else's messages in the group chat, and lets yours sit on read."
        ),
        "verified_origin": (
            "First recorded by Sir Walter Scott in The Antiquary, 1816, in "
            "Scots ('cauld shouther'), in the figurative sense of an icy "
            "reception; the earliest OED instances don't refer to food, "
            "pointing to the physical gesture of turning the shoulder."
        ),
        "popular_myth": (
            "Commonly said to come from serving unwanted guests a cold "
            "shoulder of mutton. No evidence supports the food story; it's "
            "folk etymology."
        ),
        "confidence": "solid",
        "era": "19th",
        "image_style": (
            "19th-century drawing room, an elegantly dressed woman turning "
            "away with a raised shoulder from a bowing visitor, other "
            "guests conversing in the background, period furniture"
        ),
    },
    {
        "id": "barking_wrong_tree",
        "idiom": "barking up the wrong tree",
        "story": (
            "The American frontier, 1830s. A raccoon hunt runs on trust: "
            "the dogs chase the raccoon up a tree in the dark, then stand "
            "at the trunk barking until the hunter arrives with a lantern. "
            "Except raccoons learned the trick -- cross through the "
            "branches, drop, and slip away, leaving the dogs howling with "
            "total confidence at a tree holding nothing. Frontier writers "
            "like Davy Crockett's chroniclers put the phrase in print by "
            "1832."
        ),
        "reveal": "barking up the wrong tree",
        "use": (
            "It's storming into the kitchen to blame your brother for the "
            "missing biscuits while the dog licks crumbs off its nose."
        ),
        "verified_origin": (
            "From American raccoon hunting, where dogs bark at the base of "
            "a tree the quarry has already escaped. First known print use: "
            "James Kirke Paulding's Westward Ho!, 1832; also in Sketches "
            "and Eccentricities of Col. David Crockett, 1833."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "19th",
        "image_style": (
            "19th-century night forest scene, hunting dogs barking up at a "
            "bare tree, a hunter approaching with a lantern, a raccoon "
            "silhouette escaping along a branch of a neighboring tree"
        ),
    },
    {
        "id": "three_sheets_wind",
        "idiom": "three sheets to the wind",
        "story": (
            "On a sailing ship, the 'sheets' aren't sails -- they're the "
            "ropes that pin the sail corners down. Let one loose and the "
            "sail flaps; the ship wobbles. Let three go and the canvas "
            "thrashes uselessly while the ship staggers wherever the sea "
            "shoves it. Sailors turned that into a sliding scale for their "
            "shipmates: one sheet in the wind, merry; two, unsteady -- a "
            "preacher's journal from 1813 tuts about tavern keepers being "
            "'two sheets in the wind'. Three sheets: falling-down gone."
        ),
        "reveal": "three sheets to the wind",
        "use": (
            "It's the uncle at the wedding reception who has moved from "
            "dancing to explaining his business plan to a chair."
        ),
        "verified_origin": (
            "Nautical: sheets are the ropes controlling sail corners; loose "
            "sheets make the ship lurch like a drunk. Sailors used a scale "
            "of drunkenness in sheets. In print by 1813 ('two sheets in the "
            "wind', Journal of Rev. Francis Asbury) and 1821 ('three sheets "
            "in the wind', Pierce Egan's Real Life in London)."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "19th",
        "image_style": (
            "19th-century sailing ship deck in a stiff wind, loose ropes "
            "whipping about and a sail flapping free, one sailor staggering "
            "while others haul lines, sea spray over the rail"
        ),
    },
    {
        "id": "burn_midnight_oil",
        "idiom": "burning the midnight oil",
        "story": (
            "1635. The poet Francis Quarles writes about the cost of hard "
            "work: 'we spend our mid-day sweat, our mid-night oyle.' Before "
            "electricity, working past dark wasn't a vibe -- it was a "
            "purchase. Lamp oil was real money, and burning it at midnight "
            "meant the work mattered enough to pay for the light. The "
            "phrase has outlived the lamp by two centuries."
        ),
        "reveal": "burning the midnight oil",
        "use": (
            "Students cramming at 1am with a table lamp are living the "
            "discount version -- same midnight, the oil now costs almost "
            "nothing."
        ),
        "verified_origin": (
            "'Midnight oil' coined in print by Francis Quarles, Emblems, "
            "1635 ('Wee spend our mid-day sweat, or mid-night oyle'), from "
            "the literal cost of burning lamp oil to work after dark; the "
            "'burning' phrasing became standard in the 19th century."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "17th",
        "image_style": (
            "17th-century scholar's study at night, a man writing at a "
            "cluttered desk by the light of a single oil lamp, dark window "
            "behind him, books and papers stacked around"
        ),
    },
    {
        "id": "spill_the_beans",
        "idiom": "spill the beans",
        "story": (
            "English speakers had been 'spilling' secrets for centuries -- "
            "the verb meant letting something out as far back as the 1500s. "
            "Then, in early 1900s America, somebody garnished it. Horse-race "
            "writers and small-town reporters started saying a talker had "
            "'spilled the beans', and the phrase stuck fast within a "
            "decade. The beans were never anything -- just flavor thrown on "
            "a very old verb."
        ),
        "reveal": "spill the beans",
        "use": (
            "It's what your six-year-old does four days before the surprise "
            "party, at full volume, to the person the party is for."
        ),
        "verified_origin": (
            "The idiom is early 20th-century American; 'spill' in the sense "
            "of divulge dates to at least the 16th century, and 'the beans' "
            "was added for color. First print appearances are from the "
            "1900s-1910s in the US."
        ),
        "popular_myth": (
            "Often traced to an ancient Greek voting system using white and "
            "black beans, spilled prematurely. The phrase appears ~2,400 "
            "years too late for that to be the source, with no trace in "
            "between."
        ),
        "confidence": "solid",
        "era": "20th",
        "image_style": (
            "early 20th-century American general store, a tipped-over sack "
            "spilling dried beans across a wooden counter, a startled "
            "shopkeeper and two customers looking down at the mess"
        ),
    },
    {
        "id": "rule_of_thumb",
        "idiom": "rule of thumb",
        "story": (
            "A 17th-century workshop. No tape measure in reach -- but a "
            "carpenter always carries a ruler on his hand: the first joint "
            "of the thumb, close enough to an inch to trust. Brewers "
            "tested with a thumb, tailors measured cloth by it. 'Rule' "
            "here means ruler, the measuring kind, and the phrase is on "
            "record by 1692 meaning what it means now: a rough, practical "
            "guide that works."
        ),
        "reveal": "a rule of thumb",
        "use": (
            "One glass of water per hour in the sun. Not science, exactly. "
            "A rule of thumb -- measured, as always, by the body you "
            "brought with you."
        ),
        "verified_origin": (
            "Recorded since 1692; derives from using the thumb (whose first "
            "joint is roughly an inch) as an improvised measuring tool -- "
            "'rule' in the sense of ruler. The wife-beating 'law' origin is "
            "false: no such law existed, and the association only arose in "
            "the 1970s from a rumor about 18th-century judge Francis "
            "Buller, who is not recorded as ever saying it."
        ),
        "popular_myth": (
            "The claim that it comes from a law allowing a man to beat his "
            "wife with a stick no thicker than his thumb. No such law is "
            "documented; the association dates from the 1970s."
        ),
        "confidence": "solid",
        "era": "17th",
        "image_style": (
            "17th-century carpenter's workshop, a craftsman measuring a "
            "wooden plank with his thumb, tools and wood shavings on the "
            "bench, an apprentice watching"
        ),
    },
    {
        "id": "butter_up",
        "idiom": "butter someone up",
        "story": (
            "England, the 1600s. Preachers had a vivid insult for smooth "
            "talkers: flatterers 'oil their tongues and butter their lips', "
            "one religious writer complained in 1662, so their soft "
            "speeches slide into men's minds. Flattery as grease -- words "
            "made slippery so they go down easy. By 1798 the phrase had "
            "its modern shape: 'we must butter him up with kind looks and "
            "civil speeches until he signs the deed.'"
        ),
        "reveal": "buttering them up",
        "use": (
            "It's complimenting your manager's presentation skills two "
            "days before the leave request goes in."
        ),
        "verified_origin": (
            "From 17th-century English use of 'butter' for smooth "
            "flattering speech (a 1662 religious text describes flatterers "
            "who 'butter their lips'); 'butter up' with 'up' appears by "
            "1798. The Indian temple ghee-throwing origin is unevidenced "
            "folk etymology."
        ),
        "popular_myth": (
            "A widely repeated story claims it comes from an ancient Indian "
            "custom of throwing balls of ghee at temple statues to seek "
            "favor. No evidence connects the English idiom to that practice."
        ),
        "confidence": "solid",
        "era": "18th",
        "image_style": (
            "18th-century dining room, one man leaning close to flatter a "
            "seated wealthy gentleman at a table set with a large butter "
            "dish and bread, candlelight, ingratiating body language"
        ),
    },
    {
        "id": "once_blue_moon",
        "idiom": "once in a blue moon",
        "story": (
            "In the 1500s, saying 'the moon is blue' was how you called "
            "something absurd -- like saying black is white. A pamphlet "
            "from 1528 already jokes about it. So 'once in a blue moon' "
            "meant never, flat out. Then the world played a trick: in 1883 "
            "Krakatoa erupted and threw so much ash into the sky that for "
            "months, people around the planet looked up and saw a moon "
            "tinged actually, visibly blue. The impossible had a date. And "
            "the phrase drifted from 'never' to where it sits now: almost "
            "never."
        ),
        "reveal": "once in a blue moon",
        "use": (
            "It's how often the whole family manages to be in one photo "
            "with everyone's eyes open."
        ),
        "verified_origin": (
            "From the 16th-century expression that 'the moon is blue' as a "
            "byword for the impossible (in print 1528); the modern 'very "
            "rarely' sense dates to 1821 (Pierce Egan). After Krakatoa's "
            "1883 eruption, atmospheric ash genuinely made the moon appear "
            "blue in many places."
        ),
        "popular_myth": None,
        "confidence": "solid",
        "era": "19th",
        "image_style": (
            "19th-century town street at night, people pointing up at a "
            "large full moon with an unusual glow, rooftops and chimneys "
            "silhouetted, hazy sky"
        ),
    },

    # -------------------------------------------- contested, hedge the gap
    {
        "id": "turn_blind_eye",
        "idiom": "turn a blind eye",
        "story": (
            "Copenhagen, 1801. Admiral Nelson's cautious superior hoists "
            "the signal to withdraw from battle. Nelson -- who had lost "
            "most of the sight in one eye years earlier -- is said to have "
            "raised his telescope to that eye and announced he saw no "
            "signal. The famous telescope moment may be theatre polished "
            "in the retelling; what's documented is that the signal flew "
            "and Nelson carried on fighting, and won."
        ),
        "reveal": "turning a blind eye",
        "use": (
            "It's the librarian who definitely notices you whispering and "
            "has decided, today, not to see it."
        ),
        "verified_origin": (
            "At the Battle of Copenhagen, 1801, Admiral Parker signalled "
            "withdrawal and Nelson disregarded it and continued the "
            "attack -- that much is documented. The telescope-to-the-blind-"
            "eye flourish is likely embellished (Nelson was not fully "
            "blind and accounts differ), and the phrase may predate the "
            "battle; his fame helped fix it in the language."
        ),
        "popular_myth": (
            "The polished version where the whole idiom springs, verbatim, "
            "from Nelson dramatically holding a telescope to a fully blind "
            "eye. The event is real; the cinematic details and the phrase's "
            "invention there are not established."
        ),
        "confidence": "contested",
        "era": "19th",
        "image_style": (
            "19th-century naval battle scene, an admiral on a ship's "
            "quarterdeck raising a telescope to his eye, signal flags "
            "flying from a distant ship, cannon smoke over the water"
        ),
    },
    {
        "id": "mad_as_hatter",
        "idiom": "mad as a hatter",
        "story": (
            "In 18th- and 19th-century hat workshops, felt was made with a "
            "mercury compound. Hatters breathed it for years, and many "
            "developed tremors, slurred speech, and hallucinations -- in "
            "the American hat town of Danbury they just called it the "
            "Danbury Shakes. The phrase 'mad as a hatter' shows up in "
            "print in 1829, decades before Lewis Carroll borrowed it. The "
            "honest wrinkle: English already had 'mad as a March hare' and "
            "others, so whether the poisoned hatters truly birthed the "
            "phrase, or just made it ring true, is still argued."
        ),
        "reveal": "mad as a hatter",
        "use": (
            "Today it's affectionate -- the aunty who talks to her plants "
            "individually, by name, is mad as a hatter and everyone loves "
            "her for it."
        ),
        "verified_origin": (
            "Mercury poisoning among hat-makers (erethism, the 'Danbury "
            "Shakes') is documented industrial history; the phrase is in "
            "print by 1829 (Blackwood's Magazine), well before Alice in "
            "Wonderland. But older 'mad as...' phrases existed, so the "
            "mercury link as the phrase's actual source is plausible yet "
            "unproven."
        ),
        "popular_myth": (
            "That the phrase was coined by Lewis Carroll for his Hatter "
            "character. Carroll borrowed an existing expression."
        ),
        "confidence": "contested",
        "era": "19th",
        "image_style": (
            "19th-century hat-making workshop, a hatter working felt over "
            "a steaming basin, rows of top hats on wooden stands, another "
            "worker with an unsteady posture in the background"
        ),
    },
    {
        "id": "cold_turkey",
        "idiom": "quit cold turkey",
        "story": (
            "Early 1900s America had an expression: to 'talk turkey' -- "
            "and, sharper, to 'talk cold turkey' -- meaning to speak plain, "
            "no seasoning, no garnish. Blunt like a plate of leftover "
            "turkey: no preparation at all. Around 1921 doctors and "
            "newspapers began applying it to the bluntest possible way "
            "off a drug -- stopping outright, no taper, no cushion. The "
            "goosebumps-like-a-plucked-bird story came later, pinned on "
            "after the fact."
        ),
        "reveal": "quitting cold turkey",
        "use": (
            "It's deleting the app entirely on Sunday night instead of "
            "promising yourself 'just ten minutes' every day."
        ),
        "verified_origin": (
            "First recorded 1910 (Robert Service); the addiction-withdrawal "
            "sense is recorded by 1921. Most likely from 'talk (cold) "
            "turkey', meaning blunt, unprepared plain-dealing. The exact "
            "route is still debated among etymologists."
        ),
        "popular_myth": (
            "That it describes a withdrawing addict's clammy, goosebumped "
            "skin resembling a plucked turkey. The phrase's earliest uses "
            "have nothing to do with withdrawal, so this fails as the "
            "origin."
        ),
        "confidence": "contested",
        "era": "20th",
        "image_style": (
            "early 20th-century kitchen, a man pushing away an untouched "
            "plate with a whole cold roast bird on the table, determined "
            "expression, plain wooden furniture"
        ),
    },
    {
        "id": "white_elephant",
        "idiom": "a white elephant",
        "story": (
            "In old Siam -- today's Thailand -- a white elephant was "
            "sacred. It couldn't be worked, couldn't be sold, and had to "
            "be kept in splendor for life. That much is real, recorded by "
            "European travelers from the 1600s. The delicious part is the "
            "legend that grew on top: that a king displeased with a "
            "courtier would gift him one -- an honor impossible to refuse, "
            "with upkeep ruinous enough to sink him. Whether any king "
            "actually ran that scheme, nobody has proven."
        ),
        "reveal": "a white elephant",
        "use": (
            "It's the treadmill bought in January: too expensive to throw "
            "out, too unused to justify, quietly eating a corner of the "
            "bedroom."
        ),
        "verified_origin": (
            "White elephants' sacred status and costly upkeep in Siam are "
            "documented (English print references from 1663); the tale of "
            "kings gifting them to ruin courtiers circulates in print from "
            "the 1850s but is likely legend rather than verified royal "
            "practice."
        ),
        "popular_myth": (
            "The courtier-ruining gift told as established historical "
            "fact. It's the story that carried the idiom, but it isn't "
            "documented practice."
        ),
        "confidence": "contested",
        "era": "19th",
        "image_style": (
            "19th-century Siamese royal courtyard, a magnificent white "
            "elephant draped in ornate coverings, attendants with parasols "
            "and offerings, palace spires behind"
        ),
    },
    {
        "id": "paint_town_red",
        "idiom": "paint the town red",
        "story": (
            "The night of April 6, 1837, the Marquis of Waterford and his "
            "hunting friends rolled drunk into the English town of Melton "
            "Mowbray, found barrels of red paint at a toll gate, and "
            "painted it -- doors, a swan statue, the toll keeper, and at "
            "least one constable. All documented; he paid in court for it. "
            "Here's the honest catch: the phrase itself doesn't show up in "
            "print until 1883, in America. So either the story crossed the "
            "ocean and waited fifty years, or the phrase was born twice."
        ),
        "reveal": "painting the town red",
        "use": (
            "These days it's harmless: exam results out, whole friend "
            "group out for dinner, dessert twice, home at 2am."
        ),
        "verified_origin": (
            "The Marquis of Waterford's red-paint rampage in Melton "
            "Mowbray, 6 April 1837, is documented fact. The phrase's first "
            "known print use is 1883 in the United States, and the link "
            "between the two is unproven; competing explanations (red-light "
            "districts, drink-flushed faces) also lack proof."
        ),
        "popular_myth": (
            "That the Waterford incident is the confirmed, direct source "
            "of the phrase. It's a documented event but an unproven "
            "etymology."
        ),
        "confidence": "contested",
        "era": "19th",
        "image_style": (
            "19th-century English market town at night, laughing men in "
            "hunting coats daubing red paint on a shop door and a statue, "
            "one holding a lantern, overturned paint pot on the cobbles"
        ),
    },
    {
        "id": "piece_of_cake",
        "idiom": "a piece of cake",
        "story": (
            "The trail starts at the cakewalk: a 19th-century American "
            "contest, first performed by enslaved Black dancers whose "
            "graceful, exaggerated promenade quietly mocked the manners of "
            "the plantation house -- the best pair won a cake. From there, "
            "'cakewalk' and 'takes the cake' seeped into English for "
            "things done with easy style. The exact phrase arrives oddly "
            "late: Ogden Nash, 1936 -- 'life's a piece of cake'. Then RAF "
            "pilots in the Second World War made it their understatement "
            "of choice for a mission that went clean."
        ),
        "reveal": "a piece of cake",
        "use": (
            "It's what your friend says about the driving test after "
            "passing it, having described it as certain doom that morning."
        ),
        "verified_origin": (
            "Cake-as-ease imagery traces to the 19th-century American "
            "cakewalk, a dance contest originated by enslaved Black "
            "Americans satirizing plantation-owner manners, with a cake as "
            "prize. The exact phrase 'a piece of cake' first appears in "
            "Ogden Nash's Primrose Path, 1936, and was popularized by RAF "
            "pilots in WWII. The cakewalk-to-phrase route is widely cited "
            "but not definitively proven."
        ),
        "popular_myth": (
            "That RAF pilots coined it. They popularized an existing "
            "phrase."
        ),
        "confidence": "contested",
        "era": "20th",
        "image_style": (
            "1940s airfield scene, two pilots in flight jackets walking "
            "away from a parked propeller aircraft, one gesturing "
            "casually mid-conversation, hangar and windsock behind"
        ),
    },
    {
        "id": "break_a_leg",
        "idiom": "break a leg",
        "story": (
            "Backstage, the 1920s, New York. Actors -- superstitious as "
            "sailors -- won't say 'good luck'; luck named out loud is luck "
            "scared away. The wish that took its place probably crossed "
            "the Atlantic with German and Yiddish theatre folk: 'Hals- und "
            "Beinbruch' -- neck and leg fracture -- itself likely a "
            "mangling of a Hebrew blessing for success. A blessing "
            "disguised as an injury, smuggled through two languages, so "
            "the luck arrives unrecognized."
        ),
        "reveal": "break a leg",
        "use": (
            "Said at every school annual day since: a kid in costume, "
            "terrified, and someone whispering the one injury that means "
            "'you'll be great'."
        ),
        "verified_origin": (
            "American theatre slang first attested in the 1920s-30s. The "
            "leading scholarly theory routes it through German 'Hals- und "
            "Beinbruch' via Yiddish-speaking theatre communities, possibly "
            "from Hebrew 'hatzlacha u-vracha' (success and blessing). "
            "Origin remains formally unproven; rival theories exist."
        ),
        "popular_myth": (
            "Various colorful claims: bowing so deep you break a leg, "
            "John Wilkes Booth's leap, the stage's 'leg line'. None has "
            "documentary support."
        ),
        "confidence": "contested",
        "era": "20th",
        "image_style": (
            "1920s theatre backstage, an actor in costume at a dressing "
            "table mirror ringed with bulbs, a stagehand leaning in to "
            "whisper encouragement, ropes and curtain edge visible"
        ),
    },
    {
        "id": "bite_off_more",
        "idiom": "bite off more than you can chew",
        "story": (
            "1800s America, where chewing tobacco came in solid plugs and "
            "the polite move was to bite off a modest piece. Some men, "
            "offered the plug, bit off a wad far past what their jaw could "
            "work -- greed measured in cheek-bulge. Frontier newspapers "
            "were using the phrase for over-reachers by the 1870s, and "
            "it never needed updating."
        ),
        "reveal": "bitten off more than he could chew",
        "use": (
            "It's saying yes to organizing the wedding, the office "
            "offsite, and the housing society AGM -- in the same month."
        ),
        "verified_origin": (
            "American, 19th century; commonly tied to biting oversized "
            "chunks from plugs of chewing tobacco, with the figurative "
            "sense established in print by the 1870s-1880s. The tobacco "
            "route is the standard account but rests on period custom "
            "rather than a single documented coining."
        ),
        "popular_myth": None,
        "confidence": "contested",
        "era": "19th",
        "image_style": (
            "19th-century American general store porch, one man offering "
            "another a plug of tobacco, the second man biting an "
            "exaggerated piece, onlookers amused, barrels and storefront "
            "signage behind"
        ),
    },

    # ------------------------------------------------- folklore, own it
    {
        "id": "raining_cats_dogs",
        "idiom": "raining cats and dogs",
        "story": (
            "Nobody knows. That's the story. The phrase has been in print "
            "since the 1700s -- Jonathan Swift used it in 1738 -- and for "
            "three centuries people have invented explanations: animals "
            "washed off thatched roofs (a good roof sheds water; nothing "
            "sleeps on the outside of it in a storm), Norse storm gods "
            "with their cats and dogs, drowned strays floating down "
            "flooded gutters. Every theory has been chased down; none "
            "holds. Some phrases are just weather made of nonsense, "
            "passed down because they're fun to say."
        ),
        "reveal": "raining cats and dogs",
        "use": (
            "Which you'll say next monsoon, joining three hundred years "
            "of people who also had no idea why."
        ),
        "verified_origin": (
            "Origin unknown. In print by the early 18th century (Jonathan "
            "Swift, Polite Conversation, 1738). The thatched-roof story is "
            "debunked; Norse-myth and 'catadupe' (waterfall) theories lack "
            "evidence. It is honestly an unsolved phrase."
        ),
        "popular_myth": (
            "That animals sheltering in thatched roofs slid off in heavy "
            "rain. Thatch sheds water and animals don't shelter on top of "
            "it; the story is false."
        ),
        "confidence": "folklore",
        "era": "18th",
        "image_style": (
            "18th-century London street in torrential rain, people running "
            "with coats held over their heads, rainwater rushing down the "
            "gutter, dramatic storm clouds, a startled cat and dog "
            "sheltering under a cart"
        ),
    },
    {
        "id": "whole_nine_yards",
        "idiom": "the whole nine yards",
        "story": (
            "This one is famous among word researchers as the phrase they "
            "couldn't crack -- one called it a great etymological mystery "
            "of our time. The trail dead-ends in early-1900s small-town "
            "Indiana, where it first appears meaning simply 'the whole "
            "lot'. The explanations people swear by -- WWII machine-gun "
            "belts nine yards long, Scottish kilts cut from nine yards of "
            "cloth -- were all invented later, walking backwards from the "
            "number. Nine yards of what? Nobody has ever found out."
        ),
        "reveal": "the whole nine yards",
        "use": (
            "Meanwhile it works perfectly: the birthday had a theme, a "
            "cake tower, return gifts, a drone photographer -- the whole "
            "nine yards."
        ),
        "verified_origin": (
            "Origin unknown -- called 'one of the great etymological "
            "mysteries of our time' (William Safire). Earliest known "
            "idiomatic use: 1907, southern Indiana. No proposed theory "
            "(WWII ammunition belts, kilts, football, sailing) has "
            "contemporary evidence; researchers regard the theories as "
            "back-formations."
        ),
        "popular_myth": (
            "That WWII fighter ammunition belts were nine yards long, and "
            "firing them all was 'giving the whole nine yards'. No wartime "
            "evidence exists, and the phrase predates WWII."
        ),
        "confidence": "folklore",
        "era": "20th",
        "image_style": (
            "early 20th-century study, a man at a desk piled with open "
            "books and papers, holding a magnifying glass over a single "
            "small newspaper clipping, wall of bookshelves behind"
        ),
    },
    {
        "id": "under_the_weather",
        "idiom": "under the weather",
        "story": (
            "The story sailors have handed down: on a rough crossing, a "
            "seasick or feverish sailor was sent below deck -- down where "
            "the rolling was gentlest, literally under the weather raging "
            "above. Some old accounts stretch it to 'under the weather "
            "bow', the corner of the ship the storm hits first. It's "
            "tidy, it's charming, and here's the honest part: the written "
            "trail is thin. The phrase surfaces in the early 1800s "
            "meaning 'unwell', already ashore, its ship's papers missing."
        ),
        "reveal": "under the weather",
        "use": (
            "Now it's the official phrase of the Monday morning message "
            "to the boss -- 'feeling a bit under the weather' -- no deck, "
            "no storm, just a blanket and tea."
        ),
        "verified_origin": (
            "In use since the early 19th century meaning slightly unwell. "
            "The nautical explanation (sick sailors sent below deck, or "
            "'under the weather bow') is the widely repeated account but "
            "is not well documented in period sources; it should be told "
            "as sailors' lore, not established fact."
        ),
        "popular_myth": (
            "The below-deck story stated as documented naval procedure "
            "and certain origin. It's plausible lore with a thin paper "
            "trail."
        ),
        "confidence": "folklore",
        "era": "19th",
        "image_style": (
            "19th-century sailing ship in heavy seas, one sailor climbing "
            "down a hatchway ladder below deck while waves crash over the "
            "bow above, others working the rigging in the storm"
        ),
    },
    {
        "id": "let_cat_out_bag",
        "idiom": "let the cat out of the bag",
        "story": (
            "The tale generations have passed along: a crooked market "
            "trader sells you a piglet in a tied sack, except the sack he "
            "hands over holds a stray cat -- and the scam survives only "
            "until someone opens the bag and the cat bolts out, secret "
            "gone. Told for centuries. Proven never. Word researchers "
            "have hunted for a real cat-for-pig market scam behind the "
            "phrase and found nothing but the story itself, retold. What "
            "is certain: English speakers have been letting cats out of "
            "bags since at least the 1760s."
        ),
        "reveal": "let the cat out of the bag",
        "use": (
            "It's still what happens when the WhatsApp group for the "
            "surprise accidentally includes the birthday girl."
        ),
        "verified_origin": (
            "In print by the 1760s meaning to reveal a secret. No "
            "documented origin: the pig-in-a-sack market-scam explanation "
            "is unsupported by evidence and considered a probable "
            "after-the-fact invention by serious etymology sources. The "
            "legend itself, honestly labeled, is the only story there is."
        ),
        "popular_myth": (
            "The market-scam story presented as documented history. It's "
            "an old, unproven legend -- tellable only as such."
        ),
        "confidence": "folklore",
        "era": "18th",
        "image_style": (
            "18th-century market square, a startled cat leaping out of an "
            "opened sack on a market stall, a shocked buyer stepping back, "
            "a shifty trader raising his hands, market stalls and "
            "townsfolk around"
        ),
    },
]


def get_idiom(idiom_id: str) -> dict | None:
    return next((t for t in IDIOM_TOPICS if t["id"] == idiom_id), None)


def validate_idiom_bank() -> list[str]:
    """
    Self-check. Run at startup, same pattern as topics.validate_bank().

    v2: the "unknown" tier is gone -- an undocumented origin is a "folklore"
    entry told honestly as a passed-down story, not an exclusion. What still
    fails the bank: missing fields, duplicate ids, an invalid confidence
    value, or a folklore/contested entry whose verified_origin doesn't spell
    out what is and isn't documented (it must, because the critic holds the
    accuracy line with exactly that text).
    """
    problems: list[str] = []
    seen: set[str] = set()
    required = ("id", "idiom", "story", "reveal", "use", "verified_origin",
                "confidence", "era", "image_style")
    valid_confidence = {"solid", "contested", "folklore"}

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

    return problems


if __name__ == "__main__":
    from collections import Counter
    issues = validate_idiom_bank()
    tiers = Counter(t["confidence"] for t in IDIOM_TOPICS)
    print(f"{len(IDIOM_TOPICS)} idioms -- {dict(tiers)}")
    if issues:
        print("PROBLEMS:")
        for p in issues:
            print("  -", p)
    else:
        print("Bank OK.")
