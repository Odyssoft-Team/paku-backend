"""Catálogo de razas de Paku.

Cada raza tiene:
  - id:         slug canónico (PK en la tabla breeds)
  - name:       nombre de display
  - coat_group: "single" | "double" | None (mestizos / gatos sin clasificar)
  - coat_type:  uno de los 6 tipos finos, o None

Tipos de manto:
  single → simple_short          Pelo corto pegado, sin subpelo real
  single → simple_medium_long    Pelo medio/largo sin subpelo real
  single → curly_no_undercoat    Pelo rizado sin subpelo
  double → double_short          Doble manto corto
  double → double_long           Doble manto largo
  double → mixed_curly_undercoat Manto mixto / rizado con subpelo

Impacto operativo:
  - single: tiempo predecible, sin deslanado, ideal 30 min
  - double: deslanado puede aplicar, más tiempo y desgaste del groomer

Nota sobre variantes de la misma raza (ej. Pastor Alemán corto/largo):
  Se usa el id base para la variante más común en Perú. Si se requiere
  distinguir, se puede agregar un id separado en el futuro.
"""

from __future__ import annotations

from typing import Final


SPECIES_DOG: Final[str] = "dog"
SPECIES_CAT: Final[str] = "cat"


BREEDS_CATALOG: Final[list[dict]] = [
    {
        "species": SPECIES_DOG,
        "breeds": [
            # ----------------------------------------------------------------
            # Pelo simple sin subpelo — coat_group: single / simple_short
            # ----------------------------------------------------------------
            {"id": "dogo_argentino",     "name": "Dogo Argentino",              "coat_group": "single", "coat_type": "simple_short"},
            {"id": "dachshund", "name": "Dachshund (Salchicha) pelo corto", "coat_group": "single", "coat_type": "simple_short"},
            {"id": "whippet",            "name": "Whippet",                     "coat_group": "single", "coat_type": "simple_short"},
            {"id": "gran_danes",         "name": "Gran Danés",                  "coat_group": "single", "coat_type": "simple_short"},
            {"id": "pitbull",            "name": "Pitbull",                     "coat_group": "single", "coat_type": "simple_short"},
            {"id": "american_bully",     "name": "American Bully",              "coat_group": "single", "coat_type": "simple_short"},
            {"id": "boxer",              "name": "Boxer",                       "coat_group": "single", "coat_type": "simple_short"},
            {"id": "beagle",             "name": "Beagle",                      "coat_group": "single", "coat_type": "simple_short"},
            {"id": "boston_terrier",     "name": "Boston Terrier",              "coat_group": "single", "coat_type": "simple_short"},
            {"id": "fox_terrier_smooth", "name": "Fox Terrier Pelo Liso",       "coat_group": "single", "coat_type": "simple_short"},
            {"id": "dalmata",            "name": "Dálmata",                     "coat_group": "single", "coat_type": "simple_short"},
            {"id": "doberman",           "name": "Doberman",                    "coat_group": "single", "coat_type": "simple_short"},
            {"id": "weimaraner",         "name": "Weimaraner",                  "coat_group": "single", "coat_type": "simple_short"},
            {"id": "galgo",              "name": "Galgo",                       "coat_group": "single", "coat_type": "simple_short"},
            {"id": "greyhound",          "name": "Greyhound",                   "coat_group": "single", "coat_type": "simple_short"},
            {"id": "pinscher",           "name": "Pinscher",                    "coat_group": "single", "coat_type": "simple_short"},
            {"id": "chihuahua", "name": "Chihuahua pelo corto", "coat_group": "single", "coat_type": "simple_short"},
            {"id": "french_bulldog",     "name": "Bulldog Francés",             "coat_group": "single", "coat_type": "simple_short"},
            {"id": "bulldog",            "name": "Bulldog Inglés",              "coat_group": "single", "coat_type": "simple_short"},
            {"id": "basset_hound",       "name": "Basset Hound",                "coat_group": "single", "coat_type": "simple_short"},
            {"id": "bull_terrier",       "name": "Bull Terrier",                "coat_group": "single", "coat_type": "simple_short"},
            {"id": "shar_pei",           "name": "Shar Pei",                    "coat_group": "single", "coat_type": "simple_short"},
            # ----------------------------------------------------------------
            # Pelo medio o largo simple — coat_group: single / simple_medium_long
            # ----------------------------------------------------------------
            {"id": "schnauzer",          "name": "Schnauzer",                   "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "shih_tzu",           "name": "Shih Tzu",                    "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "lhasa_apso",         "name": "Lhasa Apso",                  "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "yorkshire",          "name": "Yorkshire Terrier",           "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "maltese",            "name": "Maltés",                      "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "papillon",           "name": "Papillón",                    "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "chinese_crested",    "name": "Chinese Crested",             "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "afghan_hound",       "name": "Afghan Hound",                "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "havanese",           "name": "Havanés",                     "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "dachshund_largo", "name": "Dachshund (Salchicha) pelo largo", "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "chihuahua_largo", "name": "Chihuahua pelo largo", "coat_group": "single", "coat_type": "simple_medium_long"},
            {"id": "cocker_spaniel", "name": "Cocker Spaniel corte corto", "coat_group": "single", "coat_type": "simple_medium_long"},
            # ----------------------------------------------------------------
            # Pelo rizado sin subpelo — coat_group: single / curly_no_undercoat
            # ----------------------------------------------------------------
            {"id": "poodle",             "name": "Poodle",                      "coat_group": "single", "coat_type": "curly_no_undercoat"},
            {"id": "bichon_frise",       "name": "Bichón Frisé",                "coat_group": "single", "coat_type": "curly_no_undercoat"},
            {"id": "kerry_blue_terrier", "name": "Kerry Blue Terrier",          "coat_group": "single", "coat_type": "curly_no_undercoat"},
            {"id": "bedlington_terrier", "name": "Bedlington Terrier",          "coat_group": "single", "coat_type": "curly_no_undercoat"},
            {"id": "lagotto_romagnolo",  "name": "Lagotto Romagnolo",           "coat_group": "single", "coat_type": "curly_no_undercoat"},
            {"id": "perro_agua_portugues", "name": "Perro de Agua Portugués",   "coat_group": "single", "coat_type": "curly_no_undercoat"},
            # ----------------------------------------------------------------
            # Doble manto corto — coat_group: double / double_short
            # ----------------------------------------------------------------
            {"id": "labrador",           "name": "Labrador Retriever",          "coat_group": "double", "coat_type": "double_short"},
            {"id": "pastor_aleman", "name": "Pastor Alemán pelo corto", "coat_group": "double", "coat_type": "double_short"},
            {"id": "american_eskimo",    "name": "American Eskimo",             "coat_group": "double", "coat_type": "double_short"},
            {"id": "malinois",           "name": "Pastor Belga Malinois",       "coat_group": "double", "coat_type": "double_short"},
            {"id": "australian_cattle_dog", "name": "Australian Cattle Dog",   "coat_group": "double", "coat_type": "double_short"},
            {"id": "cocker_americano",   "name": "Cocker Americano",            "coat_group": "double", "coat_type": "double_short"},
            {"id": "akita",              "name": "Akita",                       "coat_group": "double", "coat_type": "double_short"},
            {"id": "shiba_inu",          "name": "Shiba Inu",                   "coat_group": "double", "coat_type": "double_short"},
            {"id": "rottweiler",         "name": "Rottweiler",                  "coat_group": "double", "coat_type": "double_short"},
            {"id": "pug",                "name": "Pug",                         "coat_group": "double", "coat_type": "double_short"},
            {"id": "chow_chow", "name": "Chow Chow pelo corto", "coat_group": "double", "coat_type": "double_short"},
            {"id": "corgi",              "name": "Corgi",                       "coat_group": "double", "coat_type": "double_short"},
            {"id": "west_highland",      "name": "West Highland White Terrier", "coat_group": "double", "coat_type": "double_short"},
            # ----------------------------------------------------------------
            # Doble manto largo — coat_group: double / double_long
            # ----------------------------------------------------------------
            {"id": "golden_retriever",   "name": "Golden Retriever",            "coat_group": "double", "coat_type": "double_long"},
            {"id": "pastor_aleman_largo", "name": "Pastor Alemán pelo largo", "coat_group": "double", "coat_type": "double_long"},
            {"id": "chow_chow_largo", "name": "Chow Chow pelo largo", "coat_group": "double", "coat_type": "double_long"},
            {"id": "cocker_spaniel_largo", "name": "Cocker Spaniel manto largo", "coat_group": "double", "coat_type": "double_long"},
            {"id": "husky",              "name": "Husky Siberiano",             "coat_group": "double", "coat_type": "double_long"},
            {"id": "samoyedo",           "name": "Samoyedo",                    "coat_group": "double", "coat_type": "double_long"},
            {"id": "alaskan_malamute",   "name": "Alaskan Malamute",            "coat_group": "double", "coat_type": "double_long"},
            {"id": "border_collie",      "name": "Border Collie",               "coat_group": "double", "coat_type": "double_long"},
            {"id": "shetland_sheepdog",  "name": "Shetland Sheepdog",           "coat_group": "double", "coat_type": "double_long"},
            {"id": "old_english_sheepdog", "name": "Old English Sheepdog",      "coat_group": "double", "coat_type": "double_long"},
            {"id": "pomeranian",         "name": "Pomerania",                   "coat_group": "double", "coat_type": "double_long"},
            {"id": "collie",             "name": "Collie",                      "coat_group": "double", "coat_type": "double_long"},
            {"id": "bernese_mountain_dog", "name": "Boyero de Berna",           "coat_group": "double", "coat_type": "double_long"},
            {"id": "australian_shepherd", "name": "Pastor Australiano",         "coat_group": "double", "coat_type": "double_long"},
            {"id": "san_bernardo",       "name": "San Bernardo",                "coat_group": "double", "coat_type": "double_long"},
            {"id": "terranova",          "name": "Terranova",                   "coat_group": "double", "coat_type": "double_long"},
            {"id": "pekines",            "name": "Pekinés",                     "coat_group": "double", "coat_type": "double_long"},
            # ----------------------------------------------------------------
            # Manto mixto / rizado con subpelo — coat_group: double / mixed_curly_undercoat
            # ----------------------------------------------------------------
            {"id": "labradoodle",        "name": "Labradoodle",                 "coat_group": "double", "coat_type": "mixed_curly_undercoat"},
            {"id": "goldendoodle",       "name": "Goldendoodle",                "coat_group": "double", "coat_type": "mixed_curly_undercoat"},
            {"id": "cockapoo",           "name": "Cockapoo",                    "coat_group": "double", "coat_type": "mixed_curly_undercoat"},
            {"id": "bernedoodle",        "name": "Bernedoodle",                 "coat_group": "double", "coat_type": "mixed_curly_undercoat"},
            {"id": "sheepadoodle",       "name": "Sheepadoodle",                "coat_group": "double", "coat_type": "mixed_curly_undercoat"},
            {"id": "aussiedoodle",       "name": "Aussiedoodle",                "coat_group": "double", "coat_type": "mixed_curly_undercoat"},
            # ----------------------------------------------------------------
            # Mestizo — coat sin clasificar (varía por individuo)
            # ----------------------------------------------------------------
            # Mestizos (feature 0006): uno por pelaje; el cliente elige por foto. "dog_mixed" queda para
            # mascotas antiguas (se cobra con la fila "mestizo") y la migración lo desactiva.
            {"id": "dog_mixed",          "name": "Mestizo",                     "coat_group": None,     "coat_type": None, "is_active": False},
            {"id": "dog_mixed_1", "name": "Mestizo 1 · Pelo corto", "coat_group": "single", "coat_type": "simple_short", "is_mixed": True,
             "description": "Pelo corto y pegado al cuerpo."},
            {"id": "dog_mixed_2", "name": "Mestizo 2 · Pelo medio o largo", "coat_group": "single", "coat_type": "simple_medium_long", "is_mixed": True,
             "description": "Pelo liso o sedoso, de largo medio a largo, sin subpelo."},
            {"id": "dog_mixed_3", "name": "Mestizo 3 · Pelo rizado", "coat_group": "single", "coat_type": "curly_no_undercoat", "is_mixed": True,
             "description": "Pelo rizado o lanoso que crece continuamente."},
            {"id": "dog_mixed_4", "name": "Mestizo 4 · Doble manto corto", "coat_group": "double", "coat_type": "double_short", "is_mixed": True,
             "description": "Pelo corto y denso con mucho subpelo; muda bastante."},
            {"id": "dog_mixed_5", "name": "Mestizo 5 · Doble manto largo", "coat_group": "double", "coat_type": "double_long", "is_mixed": True,
             "description": "Pelo largo y muy denso con mucho subpelo."},
            {"id": "dog_mixed_6", "name": "Mestizo 6 · Mixto o rizado denso", "coat_group": "double", "coat_type": "mixed_curly_undercoat", "is_mixed": True,
             "description": "Mezcla de rizo y subpelo, muy denso."},
        ],
    },
    {
        "species": SPECIES_CAT,
        "breeds": [
            # Los gatos se clasificarán en una siguiente iteración
            {"id": "abyssinian",         "name": "Abisinio",                    "coat_group": None, "coat_type": None},
            {"id": "bengal",             "name": "Bengalí",                     "coat_group": None, "coat_type": None},
            {"id": "birman",             "name": "Birmano",                     "coat_group": None, "coat_type": None},
            {"id": "british_shorthair",  "name": "British Shorthair",           "coat_group": None, "coat_type": None},
            {"id": "burmese",            "name": "Burmés",                      "coat_group": None, "coat_type": None},
            {"id": "exotic_shorthair",   "name": "Exotic Shorthair",            "coat_group": None, "coat_type": None},
            {"id": "maine_coon",         "name": "Maine Coon",                  "coat_group": None, "coat_type": None},
            {"id": "norwegian_forest",   "name": "Noruego de Bosque",           "coat_group": None, "coat_type": None},
            {"id": "persian",            "name": "Persa",                       "coat_group": None, "coat_type": None},
            {"id": "ragdoll",            "name": "Ragdoll",                     "coat_group": None, "coat_type": None},
            {"id": "russian_blue",       "name": "Azul Ruso",                   "coat_group": None, "coat_type": None},
            {"id": "scottish_fold",      "name": "Scottish Fold",               "coat_group": None, "coat_type": None},
            {"id": "siamese",            "name": "Siamés",                      "coat_group": None, "coat_type": None},
            {"id": "sphynx",             "name": "Sphynx (Sin Pelo)",           "coat_group": None, "coat_type": None},
            {"id": "american_shorthair", "name": "American Shorthair",          "coat_group": None, "coat_type": None},
            {"id": "munchkin",           "name": "Munchkin",                    "coat_group": None, "coat_type": None},
            {"id": "oriental",           "name": "Oriental",                    "coat_group": None, "coat_type": None},
            {"id": "cat_mixed",          "name": "Mestizo",                     "coat_group": None, "coat_type": None},
        ],
    },
]
