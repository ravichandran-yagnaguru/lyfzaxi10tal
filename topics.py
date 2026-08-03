"""
concept-bot topic bank — v2, rebuilt Door-first.

CHANGE FROM v1
--------------
v1 stored topics subject-first ("explain sharding"). The generator therefore
started from the subject and had to reverse-engineer a way in. That produced
the sharding and music-chord failures: technically correct, universally
unreadable.

v2 stores every topic Door-first. The `universal_door` field is the entry
point that ~every human has personally lived, regardless of age, education,
region, or job. The generator is required to enter through it.

SCHEMA
------
id                 stable identifier, used in post_history
category           body | everyday | tech | science | psychology | money | history
prompt             what to actually explain (the mechanism)
universal_door     the lived experience that is the ONLY permitted entry point
hook_seed          seed for the opening line; <= 12 words; generator may rephrase
                   but must not raise the reading cost
dinner_table_line  the retellable sentence this post must deliver.
                   If the draft doesn't land something like this, it fails the gate.
emotion            surprise | amusement | alarm | awe | wrong
                   (rotated for variable reward — see state.py selection)
image_type         diagram | photo
photo_keywords     search query, photo topics only
photo_subject      singular noun the photo's own description must mention

BACKWARD COMPATIBILITY
----------------------
Existing selection logic reads only `id`, `category`, `image_type`,
`photo_keywords`, `photo_subject`. Those are unchanged in name and meaning,
so pick_next_topic() works untouched. New fields are additive and consumed
by generate.py / validate.py.
"""

from __future__ import annotations

import random

TOPICS: list[dict] = [

    # ---------------------------------------------------------------- BODY
    # Highest-universality category. Everyone has a body. Lead with these.
    {
        "id": "doorway_effect",
        "category": "body",
        "prompt": (
            "The doorway effect: memory is chunked by context, and physically "
            "crossing a boundary flushes the working-memory buffer tied to the "
            "previous room."
        ),
        "universal_door": "Walking into a room and instantly forgetting why.",
        "hook_seed": "You walk into the kitchen and forget why. Every time.",
        "dinner_table_line": (
            "It isn't your memory failing — the doorway itself wipes it, "
            "and walking back actually helps."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "earworms",
        "category": "body",
        "prompt": (
            "Earworms: the brain's auditory loop treats an unfinished musical "
            "phrase as an open task and rehearses it involuntarily."
        ),
        "universal_door": "A song stuck on loop in your head for a whole day.",
        "hook_seed": "That song has been in your head since morning. Here's why.",
        "dinner_table_line": (
            "Your brain loops it because it never heard the ending — "
            "playing the song all the way through usually kills it."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "own_voice",
        "category": "body",
        "prompt": (
            "Bone conduction: you normally hear your voice through skull "
            "vibration plus air, which adds low frequencies a recording lacks."
        ),
        "universal_door": "Hearing a recording of your own voice and cringing.",
        "hook_seed": "Your recorded voice sounds wrong. The recording is right.",
        "dinner_table_line": (
            "Everyone else has only ever heard the version you hate — "
            "the voice in your head is the fake one."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },
    {
        "id": "time_speeds_up",
        "category": "body",
        "prompt": (
            "Why subjective time accelerates with age: memory density. Novel "
            "experiences lay down more markers; routine compresses to almost "
            "nothing in recall."
        ),
        "universal_door": "Childhood summers felt endless. Now a year vanishes.",
        "hook_seed": "A year used to be forever. Now it's gone by March.",
        "dinner_table_line": (
            "Time doesn't speed up — you just stop making new memories, "
            "so there's nothing to measure it against."
        ),
        "emotion": "awe",
        "image_type": "diagram",
    },
    {
        "id": "hypnic_jerk",
        "category": "body",
        "prompt": (
            "Hypnic jerks: as muscles go slack at sleep onset, the brain "
            "sometimes misreads the loss of tone as falling and fires a "
            "protective startle."
        ),
        "universal_door": "Jolting awake with the feeling of falling.",
        "hook_seed": "You've felt yourself fall while lying perfectly still.",
        "dinner_table_line": (
            "Your brain briefly thinks you're falling out of a tree — "
            "it's a reflex older than the human species."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "contagious_yawning",
        "category": "body",
        "prompt": (
            "Contagious yawning as involuntary social mirroring, and the "
            "finding that it tracks emotional closeness to the yawner."
        ),
        "universal_door": "Yawning because someone near you yawned.",
        "hook_seed": "Someone yawns. You yawn. You didn't decide to.",
        "dinner_table_line": (
            "You catch yawns hardest from people you're closest to — "
            "it's a rough measure of who you actually care about."
        ),
        "emotion": "surprise",
        "image_type": "photo",
        "photo_keywords": "person yawning",
        "photo_subject": "yawn",
    },
    {
        "id": "music_chills",
        "category": "body",
        "prompt": (
            "Frisson: the chill from music arrives at moments of violated "
            "musical expectation — the reward system firing on prediction error."
        ),
        "universal_door": "Goosebumps at one specific moment in a song.",
        "hook_seed": "One moment in a song gives you chills. Always the same moment.",
        "dinner_table_line": (
            "The chill isn't beauty — it's your brain being surprised, "
            "which is why it fades once you know the song too well."
        ),
        "emotion": "awe",
        "image_type": "diagram",
    },
    {
        "id": "cant_tickle_self",
        "category": "body",
        "prompt": (
            "The cerebellum predicts the sensory result of your own movements "
            "and cancels the signal — self-generated touch is pre-subtracted."
        ),
        "universal_door": "Trying to tickle yourself and feeling nothing.",
        "hook_seed": "Try to tickle yourself. Nothing. There's a reason.",
        "dinner_table_line": (
            "Your brain deletes sensations it caused itself — "
            "which is also why you can't surprise yourself."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },

    # ----------------------------------------------------------- EVERYDAY
    # Objects and design. Universal because the object is in everyone's life.
    {
        "id": "round_airplane_windows",
        "category": "everyday",
        "prompt": (
            "Square windows concentrate stress at the corners. The de Havilland "
            "Comet losses in the 1950s traced metal fatigue to corner cracking; "
            "curves distribute the load."
        ),
        "universal_door": "Every plane window you've ever looked out of is rounded.",
        "hook_seed": "Plane windows are round. People died to learn that.",
        "dinner_table_line": (
            "Square windows tore planes apart at the corners — "
            "the curve is a lesson written in wreckage."
        ),
        "emotion": "alarm",
        "image_type": "photo",
        "photo_keywords": "airplane window seat view",
        "photo_subject": "window",
    },
    {
        "id": "placebo_buttons",
        "category": "everyday",
        "prompt": (
            "Placebo buttons: many door-close and crosswalk buttons are "
            "disconnected, retained because perceived control reduces "
            "frustration during waiting."
        ),
        "universal_door": "Jabbing the elevator close button repeatedly.",
        "hook_seed": "That elevator close button probably isn't connected to anything.",
        "dinner_table_line": (
            "It's there so you feel in control while you wait — "
            "and it genuinely works, even though the button doesn't."
        ),
        "emotion": "wrong",
        "image_type": "photo",
        "photo_keywords": "elevator buttons panel",
        "photo_subject": "button",
    },
    {
        "id": "phantom_traffic_jams",
        "category": "everyday",
        "prompt": (
            "Phantom jams: one driver braking slightly propagates backward as a "
            "compression wave, so a jam persists long after any cause is gone."
        ),
        "universal_door": "Crawling in traffic, then it clears with no accident.",
        "hook_seed": "Traffic stops. Then clears. There was never a crash.",
        "dinner_table_line": (
            "You were sitting in a wave — one person tapped their brakes "
            "twenty minutes ago and it's still travelling backwards."
        ),
        "emotion": "awe",
        "image_type": "diagram",
    },
    {
        "id": "milk_at_back",
        "category": "everyday",
        "prompt": (
            "Store layout: staples are placed furthest from the entrance so the "
            "path to them passes maximum unplanned-purchase surface area."
        ),
        "universal_door": "Walking the whole shop for one carton of milk.",
        "hook_seed": "Milk is always at the back. That's not an accident.",
        "dinner_table_line": (
            "The shop is designed so you can never buy just one thing — "
            "the walk is the product."
        ),
        "emotion": "wrong",
        "image_type": "photo",
        "photo_keywords": "supermarket dairy aisle refrigerator",
        "photo_subject": "supermarket",
    },
    {
        "id": "round_manhole_covers",
        "category": "everyday",
        "prompt": (
            "A circle is the only common shape with constant width, so a round "
            "cover cannot be rotated to fall through its own opening."
        ),
        "universal_door": "Stepping over a manhole cover on any street on earth.",
        "hook_seed": "Manhole covers are round for one very specific reason.",
        "dinner_table_line": (
            "A square cover can be turned diagonally and dropped down the hole. "
            "A circle can't fall into itself."
        ),
        "emotion": "surprise",
        "image_type": "photo",
        "photo_keywords": "manhole cover street",
        "photo_subject": "manhole",
    },
    {
        "id": "cabin_lights_dim",
        "category": "everyday",
        "prompt": (
            "Cabin lights are dimmed for night takeoff and landing so passengers' "
            "eyes are already dark-adapted if an evacuation is needed."
        ),
        "universal_door": "The cabin going dark just before landing.",
        "hook_seed": "They dim the cabin lights before landing. It's not for sleep.",
        "dinner_table_line": (
            "They're pre-adjusting your eyes to darkness in case you have to "
            "run for an exit in the next ninety seconds."
        ),
        "emotion": "alarm",
        "image_type": "photo",
        "photo_keywords": "dim airplane cabin interior night",
        "photo_subject": "cabin",
    },
    {
        "id": "gas_pump_clicks",
        "category": "everyday",
        "prompt": (
            "The auto-shutoff uses a Venturi tube: rising fuel blocks a small "
            "air hole near the nozzle tip, and the pressure drop trips the valve "
            "mechanically — no electronics."
        ),
        "universal_door": "The fuel nozzle clunking off by itself when the tank fills.",
        "hook_seed": "The fuel nozzle stops itself. Nothing electronic is involved.",
        "dinner_table_line": (
            "It's pure physics — a tiny hole gets covered by fuel and the "
            "pressure change slams the valve shut."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "ketchup_wont_pour",
        "category": "everyday",
        "prompt": (
            "Ketchup is thixotropic: it behaves as a solid at rest and thins "
            "under shear, so it resists then suddenly floods."
        ),
        "universal_door": "Nothing, nothing, nothing — then half the bottle.",
        "hook_seed": "Ketchup comes out as nothing, then far too much.",
        "dinner_table_line": (
            "Ketchup is technically a solid until you shake it — "
            "you're not pouring a liquid, you're breaking one."
        ),
        "emotion": "amusement",
        "image_type": "photo",
        "photo_keywords": "ketchup bottle pouring",
        "photo_subject": "ketchup",
    },
    {
        "id": "weep_holes",
        "category": "everyday",
        "prompt": (
            "Weep holes: small gaps left in brickwork let trapped moisture drain "
            "and ventilate the cavity behind the wall."
        ),
        "universal_door": "Small holes in the brick wall of almost every building.",
        "hook_seed": "Those little holes in brick walls aren't mistakes.",
        "dinner_table_line": (
            "Every brick wall needs to breathe — seal those holes and the "
            "wall rots from inside."
        ),
        "emotion": "surprise",
        "image_type": "photo",
        "photo_keywords": "brick wall weep holes mortar",
        "photo_subject": "brick",
    },

    # --------------------------------------------------------------- TECH
    # Tech ONLY through a door the non-technical reader has walked through.
    # Never name the mechanism in the hook.
    {
        "id": "caching",
        "category": "tech",
        "prompt": (
            "Caching: the second load is instant because the data never left "
            "your device — explain via keeping frequently used things on the "
            "desk instead of walking to the storeroom."
        ),
        "universal_door": "A video that buffered forever plays instantly on rewatch.",
        "hook_seed": "The video buffered forever. Watch it again — instant. Why?",
        "dinner_table_line": (
            "Your phone quietly kept a copy — most of the internet's speed "
            "is just not fetching things twice."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "sharding",
        "category": "tech",
        "prompt": (
            "Sharding and horizontal scale: no single machine could serve "
            "everyone, so data is split across many. Explain via one librarian "
            "versus a library split into rooms by surname."
        ),
        "universal_door": "Two billion people open the same app at breakfast.",
        "hook_seed": "Two billion people open Instagram at breakfast. It doesn't collapse.",
        "dinner_table_line": (
            "There is no 'the server' — you and your neighbour are being "
            "served by completely different machines."
        ),
        "emotion": "awe",
        "image_type": "diagram",
    },
    {
        "id": "wifi_crowded",
        "category": "tech",
        "prompt": (
            "Shared airtime: wifi is one conversation everyone takes turns in, "
            "so more devices means more waiting, not a thinner pipe."
        ),
        "universal_door": "Hotel wifi dying the moment the conference starts.",
        "hook_seed": "Hotel wifi dies when the hotel fills up. Not the reason you think.",
        "dinner_table_line": (
            "Wifi isn't a pipe being shared — it's one person talking at a "
            "time, and everyone else is queueing."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },
    {
        "id": "deleted_not_deleted",
        "category": "tech",
        "prompt": (
            "Deletion removes the index entry, not the data — the space is "
            "marked reusable. Explain via tearing out the contents page rather "
            "than the chapters."
        ),
        "universal_door": "Deleting a photo and assuming it's gone.",
        "hook_seed": "You deleted the file. It's still there.",
        "dinner_table_line": (
            "Deleting only rips out the index page — the file sits there "
            "until something else happens to land on top of it."
        ),
        "emotion": "alarm",
        "image_type": "diagram",
    },
    {
        "id": "battery_percentage",
        "category": "tech",
        "prompt": (
            "Battery percentage is an estimate from voltage curves, not a fuel "
            "gauge — which is why it jumps and why the last 10% behaves oddly."
        ),
        "universal_door": "Your phone dropping from 20% to dead in minutes.",
        "hook_seed": "Your battery percentage is a guess. Often a bad one.",
        "dinner_table_line": (
            "Nothing in your phone can actually measure how much charge is "
            "left — it's inferring it, and it gets worse as the battery ages."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },
    {
        "id": "loading_bars_lie",
        "category": "tech",
        "prompt": (
            "Progress bars are often non-linear or fabricated because perceived "
            "wait time drops when progress appears to accelerate."
        ),
        "universal_door": "A progress bar stuck at 99% forever.",
        "hook_seed": "The loading bar stuck at 99% was lying to you.",
        "dinner_table_line": (
            "Many progress bars show no real progress at all — they're "
            "designed to make waiting feel shorter, not to inform you."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },
    {
        "id": "phone_slows_down",
        "category": "tech",
        "prompt": (
            "Perceived slowdown: software grows to assume newer hardware while "
            "storage fills and the battery degrades, so the same chip does more "
            "work with less headroom."
        ),
        "universal_door": "A phone that felt fast two years ago now feels sluggish.",
        "hook_seed": "Your phone got slower. The hardware didn't change.",
        "dinner_table_line": (
            "The phone didn't slow down — the software got heavier around it "
            "while the battery quietly lost its ability to deliver peak power."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "free_apps",
        "category": "tech",
        "prompt": (
            "Attention and data as the actual product: free apps monetise "
            "predicted behaviour, so engagement design is the business model."
        ),
        "universal_door": "Apps that cost nothing yet fund enormous companies.",
        "hook_seed": "The app was free. Someone still paid for it.",
        "dinner_table_line": (
            "You're not the customer — the advertiser is, and what's being "
            "sold is a prediction about what you'll do next."
        ),
        "emotion": "alarm",
        "image_type": "diagram",
    },
    {
        "id": "airplane_mode",
        "category": "tech",
        "prompt": (
            "Airplane mode exists less for the aircraft and more for the ground "
            "network: a phone at altitude hits many towers at once. Explain the "
            "actual risk honestly rather than the myth."
        ),
        "universal_door": "Being told to switch on airplane mode, every single flight.",
        "hook_seed": "Airplane mode isn't really protecting the plane.",
        "dinner_table_line": (
            "Your phone at 30,000 feet screams at hundreds of ground towers "
            "at once — the network is what's being protected."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },

    # ------------------------------------------------------------ SCIENCE
    # Kitchen and body chemistry. The lab is everyone's house.
    {
        "id": "onion_tears",
        "category": "science",
        "prompt": (
            "Cutting ruptures cells, releasing enzymes that form a volatile "
            "sulfur compound; it reacts with eye moisture to form a mild acid, "
            "and tears are the flush response."
        ),
        "universal_door": "Crying over a chopping board.",
        "hook_seed": "Onions don't make you cry. They make acid in your eyes.",
        "dinner_table_line": (
            "The onion is releasing a gas that turns into acid the moment it "
            "touches your eye — the tears are your body rinsing it out."
        ),
        "emotion": "alarm",
        "image_type": "photo",
        "photo_keywords": "chopped onion cutting board",
        "photo_subject": "onion",
    },
    {
        "id": "cloudy_ice",
        "category": "science",
        "prompt": (
            "Ice freezes from the outside in, pushing dissolved air and "
            "impurities to the last-frozen centre — the cloud is trapped gas."
        ),
        "universal_door": "Home ice cubes are cloudy; bar ice is clear.",
        "hook_seed": "Your ice cubes are cloudy in the middle. Bar ice isn't.",
        "dinner_table_line": (
            "That cloud is trapped air — clear ice is just ice that was "
            "frozen slowly enough for the air to escape."
        ),
        "emotion": "surprise",
        "image_type": "photo",
        "photo_keywords": "ice cubes glass close up",
        "photo_subject": "ice",
    },
    {
        "id": "apple_browning",
        "category": "science",
        "prompt": (
            "Enzymatic browning: cutting exposes an enzyme to oxygen, producing "
            "pigment. Acid (lemon) slows the enzyme, which is why it works."
        ),
        "universal_door": "A cut apple going brown in your lunchbox.",
        "hook_seed": "A cut apple turns brown. It's not drying out.",
        "dinner_table_line": (
            "The apple is rusting, more or less — and a squeeze of lemon "
            "stops it by shutting the enzyme down."
        ),
        "emotion": "surprise",
        "image_type": "photo",
        "photo_keywords": "sliced apple browning",
        "photo_subject": "apple",
    },
    {
        "id": "microwave_uneven",
        "category": "science",
        "prompt": (
            "Standing waves create hot and cold spots; the turntable exists to "
            "drag food through them. Edges absorb more energy than the centre."
        ),
        "universal_door": "Food scalding at the edge and frozen in the middle.",
        "hook_seed": "Boiling at the edges, ice in the middle. Every time.",
        "dinner_table_line": (
            "There are fixed hot and cold spots inside your microwave — "
            "the turntable exists purely to smear food through both."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "spicy_sweat",
        "category": "science",
        "prompt": (
            "Capsaicin binds the heat receptor directly, so the nervous system "
            "reports burning that isn't happening and cools a body that isn't hot."
        ),
        "universal_door": "Sweating through a plate of hot food.",
        "hook_seed": "Spicy food isn't hot. Your nerves just think it is.",
        "dinner_table_line": (
            "Chilli picks the lock on your heat sensor — you sweat because "
            "your body is fighting a temperature that doesn't exist."
        ),
        "emotion": "wrong",
        "image_type": "photo",
        "photo_keywords": "red chili peppers",
        "photo_subject": "chili",
    },
    {
        "id": "bananas_ripen",
        "category": "science",
        "prompt": (
            "Ethylene gas: ripening fruit emits a hormone that triggers "
            "ripening in neighbours — a chemical broadcast."
        ),
        "universal_door": "One bad banana taking the whole bowl down with it.",
        "hook_seed": "One ripe banana ruins the bowl. It's contagious.",
        "dinner_table_line": (
            "Fruit talks to other fruit with a gas — one banana can order "
            "the entire bowl to ripen."
        ),
        "emotion": "awe",
        "image_type": "photo",
        "photo_keywords": "bananas fruit bowl ripe",
        "photo_subject": "banana",
    },
    {
        "id": "reheated_coffee",
        "category": "science",
        "prompt": (
            "Aromatic compounds are volatile and escape first; reheating drives "
            "off what's left and further oxidises bitter compounds."
        ),
        "universal_door": "Microwaving cold coffee and regretting it.",
        "hook_seed": "Reheated coffee tastes wrong. The good part already left.",
        "dinner_table_line": (
            "Most of coffee's flavour is smell, and the smell physically "
            "evaporated while the cup sat there."
        ),
        "emotion": "surprise",
        "image_type": "photo",
        "photo_keywords": "cold coffee cup mug",
        "photo_subject": "coffee",
    },
    {
        "id": "bread_stales_fridge",
        "category": "science",
        "prompt": (
            "Staling is starch retrogradation, not drying — and it runs fastest "
            "just above freezing, so the fridge is the worst place for bread."
        ),
        "universal_door": "Putting bread in the fridge to keep it fresh.",
        "hook_seed": "The fridge is the worst possible place for bread.",
        "dinner_table_line": (
            "Bread goes stale fastest at fridge temperature — the freezer is "
            "fine, the counter is fine, the fridge is the one bad option."
        ),
        "emotion": "wrong",
        "image_type": "photo",
        "photo_keywords": "sliced bread loaf",
        "photo_subject": "bread",
    },

    # --------------------------------------------------------- PSYCHOLOGY
    {
        "id": "baader_meinhof",
        "category": "psychology",
        "prompt": (
            "Frequency illusion: selective attention plus confirmation bias make "
            "a newly salient thing appear to surge in the world."
        ),
        "universal_door": "Buying a car, then seeing that car everywhere.",
        "hook_seed": "You bought the car. Now that car is everywhere.",
        "dinner_table_line": (
            "They were always there — your brain just started filing them "
            "instead of discarding them."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "zeigarnik",
        "category": "psychology",
        "prompt": (
            "The Zeigarnik effect: unfinished tasks occupy memory more "
            "persistently than completed ones — which is why cliffhangers work."
        ),
        "universal_door": "An unfinished task nagging at you all evening.",
        "hook_seed": "Finished tasks vanish from your head. Unfinished ones don't.",
        "dinner_table_line": (
            "Your brain refuses to close a loop — which is exactly why you "
            "can't stop watching a series that ends every episode mid-scene."
        ),
        "emotion": "surprise",
        "image_type": "diagram",
    },
    {
        "id": "bystander_effect",
        "category": "psychology",
        "prompt": (
            "Diffusion of responsibility: help becomes less likely as the crowd "
            "grows. Include the practical fix — address one specific person."
        ),
        "universal_door": "A crowded street where nobody stops to help.",
        "hook_seed": "In a crowd, fewer people help. Not more.",
        "dinner_table_line": (
            "If you ever need help in a crowd, point at one person and speak "
            "to them directly — a crowd helps nobody, a person helps."
        ),
        "emotion": "alarm",
        "image_type": "diagram",
    },
    {
        "id": "cringe_at_2am",
        "category": "psychology",
        "prompt": (
            "Why old embarrassments resurface at night: reduced cognitive load "
            "plus the emotional weighting that made the memory durable."
        ),
        "universal_door": "Remembering something humiliating from ten years ago, in bed.",
        "hook_seed": "It's 2am and your brain picked 2011 to relitigate.",
        "dinner_table_line": (
            "Embarrassment is stored more strongly than almost anything else — "
            "your brain filed it as a survival threat."
        ),
        "emotion": "amusement",
        "image_type": "diagram",
    },
    {
        "id": "cocktail_party",
        "category": "psychology",
        "prompt": (
            "The cocktail party effect: unattended audio is monitored below "
            "awareness, and your own name breaks through the filter."
        ),
        "universal_door": "Hearing your name across a loud room.",
        "hook_seed": "You hear your name across a loud room. You weren't listening.",
        "dinner_table_line": (
            "Something in you is listening to every conversation in the room, "
            "all the time — it just only interrupts for your name."
        ),
        "emotion": "awe",
        "image_type": "diagram",
    },
    {
        "id": "peak_end_rule",
        "category": "psychology",
        "prompt": (
            "Peak-end rule: an experience is remembered by its most intense "
            "moment and its ending, not its average or duration."
        ),
        "universal_door": "A great holiday ruined in memory by the last day.",
        "hook_seed": "You don't remember experiences. You remember two moments.",
        "dinner_table_line": (
            "Your memory scores everything by its peak and its ending — "
            "which means how something finishes matters more than how long it was good."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },
    {
        "id": "negativity_bias",
        "category": "psychology",
        "prompt": (
            "Negativity bias: threat information is processed faster and "
            "weighted heavier, which is why bad news outruns good."
        ),
        "universal_door": "Nine compliments and one criticism — you remember the one.",
        "hook_seed": "Nine people praised you. You're thinking about the tenth.",
        "dinner_table_line": (
            "Bad news is processed faster than good news because the ancestors "
            "who ignored threats didn't become anyone's ancestors."
        ),
        "emotion": "awe",
        "image_type": "diagram",
    },
    {
        "id": "spotlight_effect",
        "category": "psychology",
        "prompt": (
            "The spotlight effect: we drastically overestimate how much others "
            "notice our appearance and mistakes."
        ),
        "universal_door": "Being convinced everyone noticed the stain on your shirt.",
        "hook_seed": "Nobody noticed. You've been sure for hours that they did.",
        "dinner_table_line": (
            "Everyone is starring in their own film and you're an extra in "
            "all of them — which is oddly freeing."
        ),
        "emotion": "amusement",
        "image_type": "diagram",
    },

    # -------------------------------------------------------------- MONEY
    {
        "id": "prices_end_99",
        "category": "money",
        "prompt": (
            "Left-digit anchoring: the first digit is encoded before the rest, "
            "so 4.99 files closer to 4 than to 5."
        ),
        "universal_door": "Every price tag you have ever looked at.",
        "hook_seed": "4.99 lands in your head as four. Not five.",
        "dinner_table_line": (
            "Your brain reads the first digit and commits before it finishes "
            "the number — the 99 is aimed at that gap."
        ),
        "emotion": "wrong",
        "image_type": "photo",
        "photo_keywords": "price tag store label",
        "photo_subject": "price",
    },
    {
        "id": "slow_music_shops",
        "category": "money",
        "prompt": (
            "Tempo and pace: slower music slows walking speed, extends dwell "
            "time and raises spend — measured in supermarket field studies."
        ),
        "universal_door": "The oddly relaxed music in every supermarket.",
        "hook_seed": "The supermarket music is slow on purpose. You walk slower.",
        "dinner_table_line": (
            "Slow music makes you walk slower, and walking slower makes you "
            "buy more — it's measurable, and it's why the playlist never changes tempo."
        ),
        "emotion": "wrong",
        "image_type": "photo",
        "photo_keywords": "supermarket aisle shopping",
        "photo_subject": "supermarket",
    },
    {
        "id": "card_vs_cash",
        "category": "money",
        "prompt": (
            "The pain of paying: physical cash produces a stronger loss signal "
            "than a card tap, so identical purchases feel cheaper on card."
        ),
        "universal_door": "Tapping a card and barely registering the amount.",
        "hook_seed": "The same price hurts less on a card. Measurably less.",
        "dinner_table_line": (
            "Handing over cash physically hurts in a way tapping doesn't — "
            "which is precisely why tapping exists."
        ),
        "emotion": "alarm",
        "image_type": "photo",
        "photo_keywords": "contactless card payment terminal",
        "photo_subject": "card",
    },
    {
        "id": "decoy_effect",
        "category": "money",
        "prompt": (
            "The decoy: adding a deliberately poor third option makes the "
            "target option look obviously correct. Classic in menus and pricing tiers."
        ),
        "universal_door": "A menu with one absurdly overpriced item nobody orders.",
        "hook_seed": "That overpriced item on the menu isn't meant to be ordered.",
        "dinner_table_line": (
            "It exists to make the second-most-expensive thing look reasonable — "
            "and you ordered it, didn't you."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },
    {
        "id": "casinos_no_clocks",
        "category": "money",
        "prompt": (
            "Environment design for time distortion: no clocks, no windows, "
            "constant light and sound remove every cue for how long you've been there."
        ),
        "universal_door": "Losing track of time indoors somewhere with no windows.",
        "hook_seed": "Casinos have no clocks and no windows. Nothing there is accidental.",
        "dinner_table_line": (
            "Every cue you use to sense passing time has been deliberately "
            "removed from the room."
        ),
        "emotion": "alarm",
        "image_type": "diagram",
    },
    {
        "id": "free_shipping",
        "category": "money",
        "prompt": (
            "Zero-price effect: free is processed categorically differently from "
            "cheap, so free shipping outperforms a larger discount."
        ),
        "universal_door": "Adding items to a cart to unlock free delivery.",
        "hook_seed": "You spent more to avoid a delivery fee. Everyone does.",
        "dinner_table_line": (
            "Free isn't a low price — it's a different category in your head, "
            "and people reliably spend more money to reach it."
        ),
        "emotion": "wrong",
        "image_type": "diagram",
    },

    # ------------------------------------------------------------ HISTORY
    # Only origins attached to something the reader touches daily.
    {
        "id": "sixty_seconds",
        "category": "history",
        "prompt": (
            "Babylonian base-60 mathematics survives in clocks and angles "
            "because 60 divides cleanly by so many numbers."
        ),
        "universal_door": "Every clock you have ever read.",
        "hook_seed": "Your clock runs on a number system 4,000 years old.",
        "dinner_table_line": (
            "We count time in sixties because the Babylonians did — "
            "it's the oldest thing you use every single day."
        ),
        "emotion": "awe",
        "image_type": "photo",
        "photo_keywords": "analog clock face",
        "photo_subject": "clock",
    },
    {
        "id": "qwerty",
        "category": "history",
        "prompt": (
            "QWERTY's layout emerged from typewriter mechanics and telegraph "
            "usage, then locked in through training and network effects."
        ),
        "universal_door": "The keyboard you're reading this on.",
        "hook_seed": "Your keyboard layout was designed for a machine you've never used.",
        "dinner_table_line": (
            "The layout solved a jamming problem in 1870s typewriters, and "
            "we've been stuck with it ever since because everyone learned it."
        ),
        "emotion": "wrong",
        "image_type": "photo",
        "photo_keywords": "vintage typewriter keys",
        "photo_subject": "typewriter",
    },
    {
        "id": "driving_sides",
        "category": "history",
        "prompt": (
            "Left-versus-right driving traces to mounted travel and sword hands, "
            "then to wagon design and Napoleonic and colonial spread."
        ),
        "universal_door": "Which side of the road your country drives on.",
        "hook_seed": "Which side you drive on was decided by sword hands.",
        "dinner_table_line": (
            "Riders kept left so their sword arm faced oncoming strangers — "
            "half the world still drives on that decision."
        ),
        "emotion": "awe",
        "image_type": "photo",
        "photo_keywords": "road traffic highway cars",
        "photo_subject": "road",
    },
    {
        "id": "hello_telephone",
        "category": "history",
        "prompt": (
            "'Hello' as a telephone greeting was popularised by early telephone "
            "practice; Bell preferred 'ahoy'. The greeting spread from the device."
        ),
        "universal_door": "Saying hello when you answer a call.",
        "hook_seed": "'Hello' barely existed as a greeting before the telephone.",
        "dinner_table_line": (
            "We greet each other with a word that a machine taught us — "
            "and Bell wanted us to say 'ahoy' instead."
        ),
        "emotion": "amusement",
        "image_type": "photo",
        "photo_keywords": "antique rotary telephone",
        "photo_subject": "telephone",
    },
    {
        "id": "ring_finger",
        "category": "history",
        "prompt": (
            "The fourth-finger tradition rests on an ancient belief in a vein "
            "running to the heart — anatomically wrong, culturally permanent. "
            "Hedge the origin appropriately."
        ),
        "universal_door": "Wedding rings, on the same finger, across most of the world.",
        "hook_seed": "The ring finger was chosen for a reason that isn't true.",
        "dinner_table_line": (
            "The tradition rests on a vein to the heart that doesn't exist — "
            "and we've all just kept doing it anyway."
        ),
        "emotion": "amusement",
        "image_type": "photo",
        "photo_keywords": "wedding ring hand",
        "photo_subject": "ring",
    },
    {
        "id": "two_day_weekend",
        "category": "history",
        "prompt": (
            "The two-day weekend came from industrial scheduling and competing "
            "religious rest days, then spread through labour organising and "
            "Ford's five-day week."
        ),
        "universal_door": "Having Saturday and Sunday off.",
        "hook_seed": "The weekend is about a century old. Someone had to win it.",
        "dinner_table_line": (
            "Two days off isn't natural or ancient — it was fought for, "
            "and it's younger than the light bulb."
        ),
        "emotion": "awe",
        "image_type": "diagram",
    },
]


# --------------------------------------------------------------------------
# Compatibility helpers
# --------------------------------------------------------------------------

CATEGORIES = sorted({t["category"] for t in TOPICS})

# Emotion rotation supports variable reward: avoid repeating the same emotional
# flavour back to back. Consumed by generate.py alongside category rotation.
EMOTIONS = ["surprise", "amusement", "alarm", "awe", "wrong"]


def get_topic(topic_id: str) -> dict | None:
    """Look up a topic by id."""
    return next((t for t in TOPICS if t["id"] == topic_id), None)


def last_emotion(recent: list[dict]) -> str | None:
    """Emotion of the most recent posted entry, if any."""
    for entry in recent:
        if entry.get("status") == "posted":
            t = get_topic(entry.get("topic_id", ""))
            if t:
                return t.get("emotion")
    return None


def pick_next_topic(recent_history: list[dict], exclude_ids: set = frozenset()) -> dict:
    """Pick a topic avoiding: the most recent category, any topic id used
    within the current cycle (resets once every topic in that category has
    been used once), and any id in `exclude_ids` (topics already tried and
    rejected earlier in the SAME run — since this function is otherwise a
    pure function of `recent_history`, calling it again with unchanged
    history would just deterministically return the same topic again).
    `recent_history` is a list of {"topic_id": str, "category": str} ordered
    most-recent-first.

    Rotation happens at the CATEGORY level first (so all categories cycle
    through evenly, not just whichever two happen to tie-break first), then
    at the topic level within whichever category is chosen.
    """
    all_categories = sorted({t["category"] for t in TOPICS})
    recent_categories_immediate = {h["category"] for h in recent_history[:1]}
    used_ids = {h["topic_id"] for h in recent_history}

    def category_last_used_index(cat):
        for i, h in enumerate(recent_history):
            if h["category"] == cat:
                return i
        return len(recent_history) + 1  # never used recently — most eligible

    def available_in(cat):
        return [t for t in TOPICS if t["category"] == cat and t["id"] not in exclude_ids]

    eligible_categories = [
        c for c in all_categories if c not in recent_categories_immediate and available_in(c)
    ]
    if not eligible_categories:
        eligible_categories = [c for c in all_categories if available_in(c)]
    if not eligible_categories:
        # every single topic has been excluded this run — give up on exclusion
        eligible_categories = all_categories
        exclude_ids = frozenset()

    # Categories have uneven topic counts (6 to 9). Round-robining categories
    # without regard to size lets a small category (e.g. 6 topics) exhaust and
    # restart internally before larger categories finish their first pass,
    # producing a repeat before one full lap across the whole bank completes.
    # Prefer categories that still have an unused topic in the current lap —
    # same defensive shape as the exclusion fallbacks above: only narrow the
    # pool if doing so doesn't empty it, i.e. don't apply this once every
    # category has genuinely cycled and a new lap is starting.
    def has_unused(cat):
        return any(t["id"] not in used_ids for t in available_in(cat))

    categories_with_unused = [c for c in eligible_categories if has_unused(c)]
    if categories_with_unused:
        eligible_categories = categories_with_unused

    # Pick randomly among whichever categories are tied for "least recently
    # used" — with an empty or symmetric history every category ties, and a
    # stable sort would deterministically favor the same one (alphabetically
    # first) every single time history is empty, e.g. every fresh deploy.
    best_recency = max(category_last_used_index(c) for c in eligible_categories)
    chosen_category = random.choice([c for c in eligible_categories if category_last_used_index(c) == best_recency])

    category_topics = [t for t in TOPICS if t["category"] == chosen_category and t["id"] not in exclude_ids]
    candidates = [t for t in category_topics if t["id"] not in used_ids]
    if not candidates:
        candidates = category_topics  # every topic in this category has cycled — start over

    # Avoid repeating the same emotional flavour back to back (variable
    # reward) — but never let this filter empty the candidate set. Same
    # defensive shape as the category exclusion above. This has to happen
    # before the recency tie-break below, not after: filtering the already-
    # narrow tied-for-least-recent set leaves it too small to have room to
    # exclude anything most of the time. Filtering the full candidate pool
    # first gives it real effect while still respecting recency afterward.
    last_emo = last_emotion(recent_history)
    if last_emo is not None:
        emotion_filtered = [t for t in candidates if t.get("emotion") != last_emo]
        if emotion_filtered:
            candidates = emotion_filtered

    def topic_last_used_index(topic):
        for i, h in enumerate(recent_history):
            if h["topic_id"] == topic["id"]:
                return i
        return len(recent_history) + 1

    # Same tie-breaking fix at the topic level.
    best_topic_recency = max(topic_last_used_index(t) for t in candidates)
    tied = [t for t in candidates if topic_last_used_index(t) == best_topic_recency]

    return random.choice(tied)


def validate_bank() -> list[str]:
    """
    Self-check the bank. Run in CI or at startup — a malformed topic should
    fail loudly rather than produce a bad post at 9am.
    """
    problems: list[str] = []
    seen: set[str] = set()

    required = (
        "id", "category", "prompt", "universal_door",
        "hook_seed", "dinner_table_line", "emotion", "image_type",
    )

    for t in TOPICS:
        tid = t.get("id", "<missing id>")

        for field in required:
            if not t.get(field):
                problems.append(f"{tid}: missing required field '{field}'")

        if tid in seen:
            problems.append(f"{tid}: duplicate id")
        seen.add(tid)

        if t.get("emotion") not in EMOTIONS:
            problems.append(f"{tid}: unknown emotion {t.get('emotion')!r}")

        if t.get("image_type") == "photo":
            if not t.get("photo_keywords") or not t.get("photo_subject"):
                problems.append(f"{tid}: photo topic missing keywords/subject")
        elif t.get("image_type") != "diagram":
            problems.append(f"{tid}: image_type must be 'diagram' or 'photo'")

        # The hook is the whole product. Enforce the effort budget here.
        seed = t.get("hook_seed", "")
        if len(seed.split()) > 14:
            problems.append(f"{tid}: hook_seed too long ({len(seed.split())} words)")

    return problems


if __name__ == "__main__":
    issues = validate_bank()
    print(f"{len(TOPICS)} topics across {len(CATEGORIES)} categories: {CATEGORIES}")
    from collections import Counter
    print("by category:", dict(Counter(t["category"] for t in TOPICS)))
    print("by emotion: ", dict(Counter(t["emotion"] for t in TOPICS)))
    print("by image:   ", dict(Counter(t["image_type"] for t in TOPICS)))
    if issues:
        print("\nPROBLEMS:")
        for p in issues:
            print("  -", p)
    else:
        print("\nBank OK.")
