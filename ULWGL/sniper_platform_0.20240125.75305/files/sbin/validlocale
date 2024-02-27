#!/usr/bin/perl -w
#
# Author: Petter Reinholdtsen <pere@hungry.com>
# Date:   2002-02-23
#
# Test if the locale given as argument is a valid locale.  If it
# is not, print on stdout the string to add to /etc/locale.gen to make
# locale-gen generate the locale (if it exists at all).

use POSIX qw(setlocale LC_ALL);

my $debug = 0;

my $defaultcharset = $ENV{"DEFAULTCHARSET"} || "ISO-8859-1";

my $supportedlist = "/usr/share/i18n/SUPPORTED";

unless (defined $ARGV[0]) {
    usage();
    exit 1;
}

my $LANG = $ARGV[0];

my $loc = setlocale(LC_ALL, $LANG);
if ( ! $loc) {
    print STDERR "locale '$LANG' not available\n";

    my ($locale)   = $LANG =~ m/^([^.@]+)/;
    my ($charset)  = $LANG =~ m/^[^.]+\.([^@]+)/;
    my ($modifier) = $LANG =~ m/(@.+)$/;

    $modifier = "" unless defined $modifier;

    # Hm, if charset is missing, how to we pick the correct one to
    # use?  Fetching the value from /usr/share/i18n/SUPPORTED should
    # work on Debian.
    my $codeset = "";
    if (defined $charset) {
       $codeset = '.' . $charset;
    } else {
       $charset = get_default_charset("$locale$modifier");
    }

    # print "L: $locale C: $charset M: $modifier\n";
    print "$locale$codeset$modifier $charset\n";

    exit 1;
} else {
    print STDERR "locale '$LANG' valid and available\n";
    exit 0;
}

sub usage {
    print "Usage: $0 <locale>\n"
}

sub get_default_charset {
    my ($locale) = @_;
    my ($l, $c);
    open(SUPPORTED, "< $supportedlist") || die "Unable to open $supportedlist";
    while (<SUPPORTED>) {
	chomp;
	($l, $c) = split(/\s+/);
	print "Checking '$l' '$c' != '$locale'\n" if $debug;
	last if  ($l eq $locale);
    }
    close(SUPPORTED);

    if ($l eq $locale) {
	return $c;
    } else {
	return $defaultcharset;
    }
}
