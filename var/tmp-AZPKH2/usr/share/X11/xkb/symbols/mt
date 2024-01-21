// Maltese keyboard map (based on MSA Standard DMS100)
// by Ramon Casha (ramon.casha@linux.org.mt)

default  partial alphanumeric_keys
xkb_symbols "basic" {

    include "latin"

    name[Group1]="Maltese";

    // Copied from GB layout
    key <AE02> { [         2,   quotedbl,  twosuperior,    oneeighth ] };
    key <AE04> { [         4,     dollar,     EuroSign,   onequarter ] };
    key <AC11> { [apostrophe,         at, dead_circumflex, dead_caron] };
    key <BKSL> { [numbersign, asciitilde,   dead_grave,   dead_breve ] };

    // The following four sets are the four additional letters, with the UK
    // equivalents
    key <TLDE>	{ [ cabovedot,  Cabovedot,        grave,      notsign ]	};
    key <AD11>	{ [ gabovedot,  Gabovedot,  bracketleft,    braceleft ]	};
    key <AD12>	{ [   hstroke,    Hstroke, bracketright,   braceright ]	};
    key <LSGT>	{ [ zabovedot,  Zabovedot,    backslash,          bar ]	};

    // Euro symbol
    key <AE03>	{ [         3,   EuroSign,     sterling               ]	};

    // Long accent
    key <AE06>	{ [         6, asciicircum, dead_circumflex, dead_circumflex ]	};

    // Normal accented vowels
    key <AD03>	{ [         e,          E,       egrave,       Egrave ]	};
    key <AD07>	{ [         u,          U,       ugrave,       Ugrave ]	};
    key <AD08>	{ [         i,          I,       igrave,       Igrave ]	};
    key <AD09>	{ [         o,          O,       ograve,       Ograve ]	};
    key <AC01>	{ [         a,          A,       agrave,       Agrave ]	};

    include "level3(ralt_switch)"
};

// Maltese keyboard map (based on MSA Standard DMS100, annex A)
// by Ramon Casha (ramon.casha@linux.org.mt)

partial alphanumeric_keys
xkb_symbols "us" {

    include "latin"

    // Describes the differences between the mt
    // keyboard and a US-based physical keyboard

    name[Group1]="Maltese (with US layout)";

    // The following four sets are the four additional letters, with the US
    // equivalents
    key <TLDE>	{ [ cabovedot,  Cabovedot,        grave,   asciitilde ]	};
    key <AD11>	{ [ gabovedot,  Gabovedot,  bracketleft,    braceleft ]	};
    key <AD12>	{ [   hstroke,    Hstroke, bracketright,   braceright ]	};
    key <LSGT>	{ [ zabovedot,  Zabovedot,    backslash,          bar ]	};
    key <BKSL>	{ [ zabovedot,  Zabovedot,    backslash,          bar ]	};

    // Euro symbol
    key <AE03>	{ [         3,   EuroSign,     numbersign             ]	};

    // Long accent
    key <AE06>	{ [         6, asciicircum, dead_circumflex, dead_circumflex ]	};

    // Normal accented vowels
    key <AD03>	{ [         e,          E,       egrave,       Egrave ]	};
    key <AD07>	{ [         u,          U,       ugrave,       Ugrave ]	};
    key <AD08>	{ [         i,          I,       igrave,       Igrave ]	};
    key <AD09>	{ [         o,          O,       ograve,       Ograve ]	};
    key <AC01>	{ [         a,          A,       agrave,       Agrave ]	};

    include "level3(ralt_switch)"

};

// Alternative Maltese keyboard map (US-based layout using AltGr)
// by Johann A. Briffa (johann.briffa@um.edu.mt)

partial alphanumeric_keys
xkb_symbols "alt-us" {

    include "us(basic)"
    include "level3(ralt_switch)"

    name[Group1]="Maltese (US layout with AltGr overrides)";

    // Currency symbols
    key <AE03>  { [         3,  numbersign,    sterling,     NoSymbol ] };
    key <AE04>  { [         4,     dollar,     EuroSign,     NoSymbol ] };

    // Maltese characters
    key <AC05>  { [         g,          G,    gabovedot,    Gabovedot ] };
    key <AC06>  { [         h,          H,      hstroke,      Hstroke ] };
    key <AB01>  { [         z,          Z,    zabovedot,    Zabovedot ] };
    key <AB03>  { [         c,          C,    cabovedot,    Cabovedot ] };

    // Maltese accented vowels
    key <AD03>  { [         e,          E,       egrave,       Egrave ] };
    key <AD07>  { [         u,          U,       ugrave,       Ugrave ] };
    key <AD08>  { [         i,          I,       igrave,       Igrave ] };
    key <AD09>  { [         o,          O,       ograve,       Ograve ] };
    key <AC01>  { [         a,          A,       agrave,       Agrave ] };

    // Other accents (dead-key)
    key <TLDE>  { [     grave,  asciitilde,  dead_grave,   dead_tilde ] };
    key <AE06>  { [         6, asciicircum,    NoSymbol, dead_circumflex ] };
    key <AC11>  { [ apostrophe,   quotedbl,  dead_acute, dead_diaeresis ] };
};

// Alternative Maltese keyboard map (UK-based layout using AltGr)
// by Johann A. Briffa (johann.briffa@um.edu.mt)

partial alphanumeric_keys
xkb_symbols "alt-gb" {

    include "gb(basic)"
    include "level3(ralt_switch)"

    name[Group1]="Maltese (UK layout with AltGr overrides)";

    // Currency symbols
    key <AE03>  { [         3,   sterling,   numbersign,     NoSymbol ] };
    key <AE04>  { [         4,     dollar,     EuroSign,     NoSymbol ] };

    // Maltese characters
    key <AC05>  { [         g,          G,    gabovedot,    Gabovedot ] };
    key <AC06>  { [         h,          H,      hstroke,      Hstroke ] };
    key <AB01>  { [         z,          Z,    zabovedot,    Zabovedot ] };
    key <AB03>  { [         c,          C,    cabovedot,    Cabovedot ] };

    // Maltese accented vowels
    key <AD03>  { [         e,          E,       egrave,       Egrave ] };
    key <AD07>  { [         u,          U,       ugrave,       Ugrave ] };
    key <AD08>  { [         i,          I,       igrave,       Igrave ] };
    key <AD09>  { [         o,          O,       ograve,       Ograve ] };
    key <AC01>  { [         a,          A,       agrave,       Agrave ] };

    // Other accents (dead-key)
    key <TLDE>  { [     grave,     notsign,  dead_grave,     NoSymbol ] };
    key <AE02>  { [         2,    quotedbl,    NoSymbol, dead_diaeresis ] };
    key <AE06>  { [         6, asciicircum,    NoSymbol, dead_circumflex ] };
    key <AC11>  { [ apostrophe,         at,  dead_acute,     NoSymbol ] };
    key <BKSL>  { [numbersign,  asciitilde,    NoSymbol,   dead_tilde ] };
};

// Alternative Maltese keyboard map (US-based layout using AltGr)
// by Johann A. Briffa (johann.briffa@um.edu.mt)

partial alphanumeric_keys
xkb_symbols "alt-us" {

    include "us(basic)"
    include "level3(ralt_switch)"

    name[Group1]="Maltese (US layout with AltGr overrides)";

    // Currency symbols
    key <AE03>  { [         3,  numbersign,    sterling,     NoSymbol ] };
    key <AE04>  { [         4,     dollar,     EuroSign,     NoSymbol ] };

    // Maltese characters
    key <AC05>  { [         g,          G,    gabovedot,    Gabovedot ] };
    key <AC06>  { [         h,          H,      hstroke,      Hstroke ] };
    key <AB01>  { [         z,          Z,    zabovedot,    Zabovedot ] };
    key <AB03>  { [         c,          C,    cabovedot,    Cabovedot ] };

    // Maltese accented vowels
    key <AD03>  { [         e,          E,       egrave,       Egrave ] };
    key <AD07>  { [         u,          U,       ugrave,       Ugrave ] };
    key <AD08>  { [         i,          I,       igrave,       Igrave ] };
    key <AD09>  { [         o,          O,       ograve,       Ograve ] };
    key <AC01>  { [         a,          A,       agrave,       Agrave ] };

    // Other accents (dead-key)
    key <TLDE>  { [     grave,  asciitilde,  dead_grave,   dead_tilde ] };
    key <AE06>  { [         6, asciicircum,    NoSymbol, dead_circumflex ] };
    key <AC11>  { [ apostrophe,   quotedbl,  dead_acute, dead_diaeresis ] };
};

// Alternative Maltese keyboard map (UK-based layout using AltGr)
// by Johann A. Briffa (johann.briffa@um.edu.mt)

partial alphanumeric_keys
xkb_symbols "alt-gb" {

    include "gb(basic)"
    include "level3(ralt_switch)"

    name[Group1]="Maltese (UK layout with AltGr overrides)";

    // Currency symbols
    key <AE03>  { [         3,   sterling,   numbersign,     NoSymbol ] };
    key <AE04>  { [         4,     dollar,     EuroSign,     NoSymbol ] };

    // Maltese characters
    key <AC05>  { [         g,          G,    gabovedot,    Gabovedot ] };
    key <AC06>  { [         h,          H,      hstroke,      Hstroke ] };
    key <AB01>  { [         z,          Z,    zabovedot,    Zabovedot ] };
    key <AB03>  { [         c,          C,    cabovedot,    Cabovedot ] };

    // Maltese accented vowels
    key <AD03>  { [         e,          E,       egrave,       Egrave ] };
    key <AD07>  { [         u,          U,       ugrave,       Ugrave ] };
    key <AD08>  { [         i,          I,       igrave,       Igrave ] };
    key <AD09>  { [         o,          O,       ograve,       Ograve ] };
    key <AC01>  { [         a,          A,       agrave,       Agrave ] };

    // Other accents (dead-key)
    key <TLDE>  { [     grave,     notsign,  dead_grave,     NoSymbol ] };
    key <AE02>  { [         2,    quotedbl,    NoSymbol, dead_diaeresis ] };
    key <AE06>  { [         6, asciicircum,    NoSymbol, dead_circumflex ] };
    key <AC11>  { [ apostrophe,         at,  dead_acute,     NoSymbol ] };
    key <BKSL>  { [numbersign,  asciitilde,    NoSymbol,   dead_tilde ] };
};
