# -*- coding: utf-8 -*-
"""Built-in sample recipes for cook-forge."""

SAMPLES = [
    {
        "id": "sheet-pan-salmon",
        "name": "Sheet-pan salmon with lemon asparagus (a good recipe)",
        "note": "Well-specified: preheat, internal temp, rest, overlapping steps.",
        "text": """Title: Sheet-Pan Salmon with Lemon Asparagus
Serves: 2
Time: 30 minutes
Equipment: oven, sheet pan, cutting board, probe thermometer

Ingredients:
- 1 lb salmon fillet
- 1 bunch asparagus
- 2 tbsp olive oil
- 1 lemon
- 2 cloves garlic
- 1 tsp salt
- 1/2 tsp black pepper

Steps:
1. Preheat the oven to 425F.
2. Trim the woody ends from the asparagus and halve the lemon.
3. Toss the asparagus with 1 tbsp olive oil, salt and pepper on the sheet pan.
4. Roast the asparagus for 10 minutes.
5. Pat the salmon dry, rub it with the remaining oil, garlic and the lemon juice.
6. Set the salmon on the pan and roast for 10 to 12 minutes, until it flakes and reaches 145F in the thickest part.
7. Rest the salmon for 5 minutes before serving.
""",
    },
    {
        "id": "chili",
        "name": "Classic beef and bean chili (solid)",
        "note": "Long braise, correct order, acid present.",
        "text": """Title: Classic Beef and Bean Chili
Serves: 6
Time: 1 hour 15 minutes

Ingredients:
- 2 lb ground beef
- 1 onion
- 4 cloves garlic
- 2 tbsp chili powder
- 1 tsp cumin
- 2 cans kidney beans
- 1 can crushed tomatoes
- 2 cups beef broth
- 1 tbsp vinegar
- 1 tsp salt
- 2 tbsp oil

Steps:
1. Heat the oil in a large pot over medium heat.
2. Brown the beef for 8 minutes, breaking it up as it cooks.
3. Add the diced onion and garlic and cook for 5 minutes until soft.
4. Stir in the chili powder and cumin and toast for 1 minute.
5. Add the crushed tomatoes, broth and beans and bring to a simmer.
6. Simmer uncovered for 45 minutes, stirring occasionally, until the liquid has reduced by half.
7. Stir in the vinegar and salt and simmer for 5 minutes more.
8. Let the chili rest for 10 minutes before serving.
""",
    },
    {
        "id": "roast-chicken",
        "name": "Roast chicken for beginners (flawed on purpose)",
        "note": "Lie about the time, no preheat, no internal temp, no rest, crowded pan, 15 minute marinade.",
        "text": """Title: Roast Chicken for Beginners
Serves: 4
Time: 30 minutes

Ingredients:
- 4 lb whole chicken
- 2 tbsp butter
- 1 tbsp olive oil
- 1 tsp salt
- 1 tsp black pepper
- 1 lemon
- 1 onion
- 2 cloves garlic

Steps:
1. Rinse the chicken and pat it dry.
2. Marinate the chicken for 15 minutes.
3. Rub the chicken with butter, salt, pepper, garlic and lemon.
4. Put the chicken in a roasting pan with the onion.
5. Roast the chicken for 20 minutes.
6. Rest the chicken for 5 minutes and carve it.
""",
    },
    {
        "id": "cookies",
        "name": "Chocolate chip cookies (flawed on purpose)",
        "note": "Oven too hot, no pan rotation, no cooling, unlisted butter.",
        "text": """Title: The Best Chocolate Chip Cookies
Makes: 24 cookies
Time: 35 minutes

Ingredients:
- 2 cups flour
- 1 cup sugar
- 1 tsp baking soda
- 2 cups chocolate chips
- 1 tsp salt
- 2 eggs

Steps:
1. Preheat the oven to 450F.
2. Mix the flour, sugar, baking soda and salt together in a bowl.
3. Cream the butter and sugar, then beat in the eggs.
4. Fold the dry ingredients into the wet ingredients and stir in the chocolate chips.
5. Scoop the dough onto a baking sheet and bake for 12 minutes.
6. Serve the cookies warm right away.
""",
    },
    {
        "id": "stir-fry",
        "name": "Weeknight beef stir-fry (needs a little work)",
        "note": "Missing kit (wok), no internal temp, vague timing, unused ingredient.",
        "text": """Title: Weeknight Beef Stir-Fry
Serves: 4
Time: 25 minutes

Ingredients:
- 1.5 lb flank steak
- 2 tbsp soy sauce
- 1 tbsp cornstarch
- 1 bell pepper
- 2 cloves garlic
- 1 tbsp sesame oil
- 1 tsp salt
- 2 cups rice

Steps:
1. Slice the steak thinly against the grain.
2. Mix the steak with the soy sauce and cornstarch.
3. Heat the sesame oil in a wok over high heat.
4. Stir-fry the beef for 3 minutes until browned.
5. Add the garlic and bell pepper and stir-fry for 2 minutes.
6. Serve over rice.
""",
    },
]


def get_sample(sample_id):
    for s in SAMPLES:
        if s["id"] == sample_id:
            return s
    return None
