// based on a keyboard map from an 'xkb/symbols/be' file

default  partial alphanumeric_keys
xkb_symbols "basic" {

    include "latin"

    name[Group1]="Belgian";

    key <AE01>	{ [ ampersand,          1,          bar,   exclamdown ]	};
    key <AE02>	{ [    eacute,          2,           at,    oneeighth ]	};
    key <AE03>	{ [  quotedbl,          3,   numbersign,     sterling ]	};
    key <AE04>	{ [apostrophe,          4,   onequarter,       dollar ]	};
    key <AE05>	{ [ parenleft,          5,      onehalf, threeeighths ]	};
    key <AE06>	{ [   section,          6,  asciicircum,  fiveeighths ]	};
    key <AE07>	{ [    egrave,          7,    braceleft, seveneighths ]	};
    key <AE08>	{ [    exclam,          8,  bracketleft,    trademark ]	};
    key <AE09>	{ [  ccedilla,          9,    braceleft,    plusminus ]	};
    key <AE10>	{ [    agrave,          0,   braceright,       degree ]	};
    key <AE11>	{ [parenright,     degree,    backslash, questiondown ]	};
    key <AE12>	{ [     minus, underscore, dead_cedilla,  dead_ogonek ]	};

    key <AD01>	{ [         a,          A,           at,  Greek_OMEGA ]	};
    key <AD02>	{ [         z,          Z,      lstroke,      Lstroke ]	};
    key <AD03>	{ [         e,          E,     EuroSign,         cent ]	};
    key <AD09>  { [         o,          O,           oe,           OE ] }; // o O œ Œ
    key <AD11>	{ [dead_circumflex, dead_diaeresis,  bracketleft, dead_abovering ] };
    key <AD12>	{ [    dollar,   asterisk, bracketright,  dead_macron ]	};

    key <AC01>	{ [         q,          Q,           ae,           AE ]	};
    key <AC10>	{ [         m,          M,   dead_acute, dead_doubleacute ] };
    key <AC11>	{ [    ugrave,    percent,   dead_acute,   dead_caron ]	};
    key <TLDE>	{ [twosuperior, threesuperior,  notsign,      notsign ]	};

    key <BKSL>	{ [        mu,   sterling,   dead_grave,   dead_breve ]	};
    key <AB01>	{ [         w,          W, guillemotleft,        less ]	};
    key <AB07>	{ [     comma,   question, dead_cedilla,    masculine ]	};
    key <AB08>	{ [ semicolon,     period, horizconnector,   multiply ]	};
    key <AB09>	{ [     colon,      slash, periodcentered,   division ]	};
    key <AB10>	{ [     equal,       plus,   dead_tilde, dead_abovedot]	};
    key <LSGT>  { [      less,    greater,    backslash,    backslash ]	};

    include "level3(ralt_switch)"
};


// Variant of the fr(oss) layout for Belgium
// Copyright © 2006 Nicolas Mailhot <nicolas.mailhot @ laposte.net>
//
// ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┲━━━━━━━━━┓
// │ ³ ≤ │ 1 ≥ │ 2 É │ 3 ˘ │ 4 — │ 5 – │ 6 ™ │ 7 È │ 8 ¡ │ 9 Ç │ 0 À │ ° Ø │ _ ± ┃ ⌫ Retour┃
// │ ² ¹ │ & | │ é @ │ " # │ ' ¸ │ ( ˇ │ § ^ │ è ` │ ! ~ │ ç { │ à } │ ) ø │ - ‑ ┃  arrière┃
// ┢━━━━━┷━┱───┴─┬───┴─┬───┴─┬───┴─┬───┴─┬───┴─┬───┴─┬───┴─┬───┴─┬───┴─┬───┴─┬───┺━┳━━━━━━━┫
// ┃       ┃ A Æ │ Z Â │ E ¢ │ R Ê │ T Þ │ Y Ÿ │ U Û │ I Î │ O Œ │ P Ô │ ¨ ˚ │ * ̨  ┃Entrée ┃
// ┃Tab ↹  ┃ a æ │ z â │ e € │ r ê │ t þ │ y ÿ │ u û │ i î │ o œ │ p ô │ ^ [ │ $ ] ┃   ⏎   ┃
// ┣━━━━━━━┻┱────┴┬────┴┬────┴┬────┴┬────┴┬────┴┬────┴┬────┴┬────┴┬────┴┬────┴┬────┺┓      ┃
// ┃        ┃ Q Ä │ S „ │ D Ë │ F ‚ │ G ¥ │ H Ð │ J Ü │ K Ï │ L   │ M Ö │ % Ù │ £ ̄  ┃      ┃
// ┃Maj ⇬   ┃ q ä │ s ß │ d ë │ f ‘ │ g ’ │ h ð │ j ü │ k ï │ l / │ m ö │ ù ' │ µ ` ┃      ┃
// ┣━━━━━━━┳┹────┬┴────┬┴────┬┴────┬┴────┬┴────┬┴────┬┴────┬┴────┬┴────┬┴────┲┷━━━━━┻━━━━━━┫
// ┃       ┃ > ≠ │ W “ │ X ” │ C ® │ V ← │ B ↑ │ N → │ ? … │ . . │ / ∕ │ + − ┃             ┃
// ┃Shift ⇧┃ < \ │ w « │ x » │ c © │ v ⍽ │ b ↓ │ n ¬ │ , ¿ │ ; × │ : ÷ │ = ~ ┃Shift ⇧      ┃
// ┣━━━━━━━╋━━━━━┷━┳━━━┷━━━┱─┴─────┴─────┴─────┴─────┴─────┴───┲━┷━━━━━╈━━━━━┻━┳━━━━━━━┳━━━┛
// ┃       ┃       ┃       ┃ ␣              Espace insécable ⍽ ┃       ┃       ┃       ┃
// ┃Ctrl   ┃Meta   ┃Alt    ┃ ␣ Espace                        ␣ ┃AltGr ⇮┃Menu   ┃Ctrl   ┃
// ┗━━━━━━━┻━━━━━━━┻━━━━━━━┹───────────────────────────────────┺━━━━━━━┻━━━━━━━┻━━━━━━━┛
partial alphanumeric_keys
xkb_symbols "oss" {

    include "fr(oss)"
    include "be(oss_frbe)"

    name[Group1]="Belgian (alt.)";
};

partial alphanumeric_keys
xkb_symbols "oss_frbe" {
    // First row
    key <TLDE>	{ [      twosuperior,    threesuperior,          onesuperior,         lessthanequal ] }; // ² ³ ¹ ≤ 
    key <AE01>	{ [        ampersand,                1,                  bar,      greaterthanequal ] }; // & 1 | ≥
    key <AE02>	{ [           eacute,                2,                   at,                Eacute ] }; // é 2 @ É
    key <AE04>	{ [       apostrophe,                4,         dead_cedilla,             0x1002014 ] }; // ' 4 ¸ — (tiret cadratin)
    key <AE05>	{ [        parenleft,                5,           dead_caron,             0x1002013 ] }; // ( 5 ˇ – (tiret demi-cadratin)
    key <AE06>	{ [          section,                6,          asciicircum,             trademark ] }; // § 6 ^ ™
    key <AE08>	{ [           exclam,                8,           asciitilde,            exclamdown ] }; // ! 8 ~ ¡
    key <AE09>	{ [         ccedilla,                9,            braceleft,              Ccedilla ] }; // ç 9 { Ç
    key <AE10>	{ [           agrave,                0,           braceright,                Agrave ] }; // à 0 } À
    key <AE11>	{ [       parenright,           degree,               oslash,              Ooblique ] }; // ) ° ø Ø 
    key <AE12>	{ [            minus,       underscore,            0x1002011,             plusminus ] }; // - _ - (tiret insécable) ±

    // Second row
    key <AD11>	{ [  dead_circumflex,   dead_diaeresis,          bracketleft,        dead_abovering ] }; // ^ ̈  [ ˚
    key <AD12>	{ [           dollar,         asterisk,         bracketright,           dead_ogonek ] }; // $ * ] ̨

    // Third row
    key <AC09>  { [                l,                L,          dead_stroke ] };
    key <BKSL>	{ [              mu,          sterling,           dead_grave,           dead_macron ] }; // µ £ ` ̄

    // Fourth row
    key <LSGT>  { [             less,          greater,            backslash,              notequal ] }; // < > \ ≠
    key <AB10>  { [            equal,             plus,           dead_tilde,             0x1002212 ] }; // = + ~ −
};


partial alphanumeric_keys
xkb_symbols "oss_latin9" {

    // Restricts the be(oss) layout to latin9 symbols

    include "fr(oss_latin9)"
    include "be(oss_frbe)"
    include "keypad(oss_latin9)"

    name[Group1]="Belgian (alt., Latin-9 only)";

    // First row
    key <TLDE>	{ [      twosuperior,    threesuperior,          onesuperior,                  less ] }; // ² ³ ¹ < 
    key <AE01>	{ [        ampersand,                1,                  bar,               greater ] }; // & 1 | >
    key <AE04>	{ [       apostrophe,                4,         dead_cedilla,                 minus ] }; // ' 4 ¸ -
    key <AE05>	{ [        parenleft,                5,           dead_caron,                 minus ] }; // ( 5 ˇ -
    key <AE06>	{ [          section,                6,          asciicircum,           asciicircum ] }; // § 6 ^ ^
    key <AE12>	{ [            minus,       underscore,                minus,             plusminus ] }; // - _ - ±

    // Second row
    key <AD12>	{ [           dollar,         asterisk,         bracketright,          dead_cedilla ] }; // $ * ] ¸

    // Third row
    key <AC09>  { [                l,                L,                    l,                     L ] }; // l L l L
    key <BKSL>	{ [              mu,          sterling,           dead_grave,       dead_circumflex ] }; // µ £ ` ^

    // Fourth row
    key <LSGT>  { [             less,          greater,            backslash,                 equal ] }; // < > \ =
    key <AB10>  { [            equal,             plus,           dead_tilde,                 minus ] }; // = + ~ -
};


partial alphanumeric_keys
xkb_symbols "oss_Sundeadkeys" {

    // Modifies the basic be(oss) layout to use the Sun dead keys

    include "be(oss)"

    // First row
    key <AE04>	{ [       apostrophe,                4,        dead_cedilla,             0x1002014 ] }; // ' 4 ¸ — (tiret cadratin)

    // Second row
    key <AD11>	{ [     dead_circumflex,  dead_diaeresis,          bracketleft,        dead_abovering ] }; // ^ ̈ [ ˚

    //Third row
    key <AC11>	{ [           ugrave,          percent,          dead_acute,                Ugrave ] }; // ù % ' Ù
    key <BKSL>	{ [              mu,          sterling,          dead_grave,           dead_macron ] }; // µ £ ` ̄

    // Fourth row
    key <AB10>  { [            equal,             plus,          dead_tilde,             0x1002212 ] }; // = + ~ −
};

partial alphanumeric_keys
xkb_symbols "oss_sundeadkeys" {

    include "be(oss_Sundeadkeys)"

    name[Group1]="Belgian (alt., with Sun dead keys)";
};


partial alphanumeric_keys
xkb_symbols "iso-alternate" {
    include "be(basic)"
    name[Group1]="Belgian (alt. ISO)";

    key <AD01>	{ [         a,          A,           ae,           AE ]	};
    key <AD02>	{ [         z,          Z, guillemotleft,        less ]	};
    key <AC01>	{ [         q,          Q,           at,  Greek_OMEGA ]	};
    key <AC10>	{ [         m,          M,           mu,    masculine ]	};
    key <AB01>	{ [         w,          W,      lstroke,      Lstroke ]	};
    key <AB07>	{ [ comma,   question, dead_cedilla, dead_doubleacute ]	};
};

partial alphanumeric_keys
xkb_symbols "sundeadkeys" {

    // Use the Sun dead keys

    include "be(basic)"
    name[Group1]="Belgian (with Sun dead keys)";

    key <AD11>	{ [dead_circumflex, dead_diaeresis, bracketleft, bracketleft] };
    key <AC11>	{ [    ugrave,    percent,  dead_acute,  dead_acute ]	};
    key <BKSL>	{ [        mu,   sterling,  dead_grave,  dead_grave ]	};
    key <AB07>	{ [     comma,  question, dead_cedilla, dead_cedilla]	};
    key <AB10>	{ [     equal,       plus,  dead_tilde,  dead_tilde ]	};
};

partial alphanumeric_keys
xkb_symbols "Sundeadkeys" {

    // Use the Sun dead keys

    include "be(sundeadkeys)"

};

partial alphanumeric_keys
xkb_symbols "nodeadkeys" {

    // Eliminates dead keys from the basic Belgian layout

    include "be(basic)"
    name[Group1]="Belgian (no dead keys)";

    key <AE12>	{ [     minus, underscore,      cedilla,       ogonek ]	};
    key <AD11>	{ [asciicircum,  diaeresis,  bracketleft,  bracketleft]	};
    key <AD12>	{ [    dollar,   asterisk, bracketright,       macron ]	};
    key <AC10>	{ [         m,          M,        acute,  doubleacute ]	};
    key <AC11>	{ [    ugrave,    percent,   apostrophe,   apostrophe ]	};
    key <BKSL>	{ [        mu,   sterling,        grave,        grave ]	};
    key <AB07>	{ [     comma,   question,      cedilla,    masculine ]	};
    key <AB10>	{ [     equal,       plus,   asciitilde,   asciitilde ]	};
};

// Wang model 724 azerty Belgium keyboard
partial alphanumeric_keys
xkb_symbols "wang" {

    include "be(basic)"
    include "keypad(legacy_wang)"
    name[Group1]="Belgian (Wang 724 AZERTY)";

    // Engravings on Wang 725-3771-ae
    key <TLDE> { [ twosuperior, threesuperior,   notsign, asciitilde ] };
    key <LSGT> { [        less,       greater, backslash,  brokenbar ] };
};

// EXTRAS:

partial alphanumeric_keys
	xkb_symbols "sun_type6" {
	include "sun_vndr/be(sun_type6)"
};
