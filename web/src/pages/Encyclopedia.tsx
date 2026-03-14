import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchEncyclopediaStats } from '@/lib/api';
import { BaroqueFlourish, CornerOrnaments, SectionHeading, StaffDivider } from '@/components/shared/Decorative';

interface ArticleMeta {
  slug: string;
  title: string;
  summary: string;
  content: (stats: Record<string, unknown>) => {
    paragraphs: string[];
    stats: { label: string; value: string }[];
    links?: { label: string; url: string }[];
  };
}

// ─── Articles ────────────────────────────────────────────────────────

const ARTICLES: ArticleMeta[] = [
  {
    slug: 'bachs-life',
    title: "Bach's Life & Musical World",
    summary: 'Eisenach to Leipzig: the posts, the patrons, the rediscovery, and why it all matters for hearing the music.',
    content: () => ({
      paragraphs: [
        'Johann Sebastian Bach was born in Eisenach in 1685 into a family of musicians so extensive that "Bach" was practically a synonym for "musician" in Thuringia. He was orphaned at ten, raised by his older brother Johann Christoph, and from an early age showed a voracious appetite for learning music by copying manuscripts.',
        'His career moved through four main posts. In Weimar (1708\u20131717), as court organist and later concertmaster, he wrote most of his great organ works: the Passacaglia in C minor (BWV 582), the "Orgelbüchlein" collection of chorale preludes, and probably the Toccata and Fugue in D minor (BWV 565), though the attribution is debated. In Cöthen (1717\u20131723), as Kapellmeister to Prince Leopold, he turned to instrumental music: the Brandenburg Concertos, the solo violin sonatas and partitas, the first book of the Well-Tempered Clavier, the cello suites.',
        'Leipzig (1723\u20131750) was the longest and most productive period. As Thomaskantor \u2014 cantor of St. Thomas\u2019s Church and director of music for the city \u2014 he was responsible for providing music for multiple churches on a weekly basis. This is when the cantatas, the passions, the Mass in B minor, the second book of the Well-Tempered Clavier, The Art of Fugue, and the Musical Offering were composed. The workload was enormous and the pay was mediocre. Bach complained to his employer more than once.',
        'Bach was respected as an organist \u2014 perhaps the greatest in Europe \u2014 and known among professionals as a formidable contrapuntist. But his music was considered old-fashioned by the time of his death in 1750. The galant style, with its simpler textures and clearer phrase structures, was already dominant. His most prominent sons, Carl Philipp Emanuel and Johann Christian, composed in the newer style and were far better known.',
        'The revival came in 1829, when the twenty-year-old Felix Mendelssohn conducted the St. Matthew Passion in Berlin \u2014 the first performance since Bach\u2019s death. The Bach-Gesellschaft was founded in 1850 to publish a complete edition of his works, and by the end of the 19th century his place as a central figure in Western music was secure.',
        'Today Bach\u2019s music is performed more often than that of almost any other composer. It appears in concert halls, churches, jazz clubs, and electronic music. It was sent into space on the Voyager Golden Record. His influence extends so far beyond "classical music" that trying to trace it becomes almost pointless \u2014 he is simply part of the musical ground we all stand on.',
      ],
      stats: [
        { label: 'Born', value: '1685, Eisenach' },
        { label: 'Died', value: '1750, Leipzig' },
        { label: 'Surviving works', value: '1,100+ (BWV catalogue)' },
      ],
      links: [
        { label: 'Complete works on IMSLP', url: 'https://imslp.org/wiki/Category:Bach,_Johann_Sebastian' },
      ],
    }),
  },
  {
    slug: 'chorale-tradition',
    title: 'The Chorale Tradition',
    summary: 'Lutheran hymn tunes set in four parts \u2014 the cornerstone of tonal harmony teaching for three centuries.',
    content: (s) => ({
      paragraphs: [
        `This corpus contains ${s.total_chorales || 361} Bach chorales. The chorale \u2014 a hymn tune harmonized in four parts \u2014 was central to Lutheran worship from the Reformation onward. Martin Luther himself wrote several of the melodies that Bach later set. By Bach\u2019s time, these tunes were deeply familiar to congregations, sung every Sunday and threaded through cantatas and passions.`,
        'Bach\u2019s chorale settings survive mostly because of their use in larger works and because C. P. E. Bach and Kirnberger gathered them into collections after his death. The "371 Chorale Harmonizations" (Breitkopf, 1780s) has been a standard textbook in tonal harmony ever since. If you studied music theory in a university, you almost certainly harmonized a Bach chorale at some point.',
        `What makes these settings extraordinary is their economy. A typical chorale has eight to twelve phrases, each lasting only a few beats. Bach uses that small space to tell a harmonic story: a departure from tonic, a brief exploration of related keys, a return, and a final cadence. Each phrase ends with a fermata \u2014 not a signal to hold the note longer, but a marker that the phrase has closed and the congregation breathes.`,
        'The soprano carries the given tune. Bach\u2019s job is the other three voices: alto, tenor, and bass. The bass is especially important \u2014 it drives the harmony and often has the most interesting melodic contour of the lower parts. The alto and tenor fill in, and when Bach is at his best, each voice sings a line that could stand on its own.',
        `Across the corpus, chorales average about ${s.avg_harmonic_events || '24'} harmonic events and ${s.avg_cadences || '5'} cadences per piece. They range from straightforward \u2014 BWV 256 in F major, a clean alternation of I and V \u2014 to astonishing \u2014 BWV 60.5, with its chromatic bass descent under "Es ist genug." If you\u2019re learning harmony, starting with these is not just traditional; it\u2019s still the fastest path into tonal thinking.`,
      ],
      stats: [
        { label: 'Chorales analyzed', value: String(s.total_chorales || 361) },
        { label: 'Avg. harmonic events', value: String(s.avg_harmonic_events || '~24') },
        { label: 'Avg. cadences', value: String(s.avg_cadences || '~5') },
      ],
      links: [
        { label: '371 Chorale Harmonizations on IMSLP', url: 'https://imslp.org/wiki/371_Vierstimmige_Choralges%C3%A4nge_(Bach,_Johann_Sebastian)' },
      ],
    }),
  },
  {
    slug: 'harmonic-language',
    title: 'Harmonic Language',
    summary: 'Keys, secondary dominants, cadences, modulation \u2014 how Bach colors a phrase and why his vocabulary is so large.',
    content: (s) => ({
      paragraphs: [
        `Bach\u2019s harmonic vocabulary is enormous compared to most of his contemporaries. Where a simpler style might use six or seven chord types, a typical Bach chorale deploys about ${s.avg_unique_chords || '14'} distinct sonorities, including inversions, seventh chords, and secondary dominants.`,
        'The key to understanding his harmony is to follow the bass line. In Bach, the bass is almost always doing something purposeful: stepping through a scale, holding a pedal point, or leaping by fourth or fifth to mark a cadential arrival. The inner voices often move as little as possible \u2014 stepping by half-tone or whole-tone. The result is that the music feels both inevitable and surprising: the chords change constantly, but each change is small enough to feel connected to the last.',
        'Secondary dominants are everywhere. V/V (the dominant of the dominant) is the most common, but Bach regularly uses V/vi, V/ii, and V/IV as well. These momentary tonicizations brighten a phrase without actually modulating. A single chorale phrase may pass through two or three brief key areas before landing on the cadence.',
        'Bach\u2019s cadences fall into clear categories: perfect authentic (V\u2013I with the soprano on the tonic), imperfect authentic, half cadence (ending on V), deceptive (V going somewhere unexpected, usually vi), and plagal (IV\u2013I). But the genius is in how he prepares them. A perfect cadence often arrives after several beats of harmonic tension \u2014 suspensions in the upper voices, chromatic passing tones in the bass \u2014 so that the resolution feels earned rather than routine.',
        `Modulation is handled with characteristic efficiency. Bach rarely needs more than one or two chords to pivot to a new key. A single chord can serve double duty: IV in C major is also I in F major. The modulation graph for most chorales shows three to five key regions, usually the relative major or minor and the dominant. The chorales pass through about ${s.total_keys || '20'} distinct key areas corpus-wide.`,
        'What makes Bach different from a textbook exercise is his willingness to break the rules when the text or the musical line demands it. A chord that "shouldn\u2019t" appear at a given point in the harmonic rhythm might show up because the bass line wants to keep moving, or because a chromatic alteration creates a color that the words need. The rules describe the norm. Bach knows the norm better than anyone, which is why his departures are so effective.',
      ],
      stats: [
        { label: 'Key areas', value: String(s.total_keys || '~20') },
        { label: 'Avg. unique chords', value: String(s.avg_unique_chords || '~14') },
        { label: 'Cadence types', value: Object.keys((s.cadence_type_distribution as Record<string, number>) || {}).join(', ') || 'PAC, IAC, HC, DC' },
      ],
    }),
  },
  {
    slug: 'voice-leading',
    title: 'Voice-Leading',
    summary: 'How the four voices stay singable, independent, and tightly woven \u2014 the single most important concept in Bach\u2019s music.',
    content: () => ({
      paragraphs: [
        'Voice-leading is the art of moving individual voices from one chord to the next so that each part makes melodic sense on its own. It is the single most important concept in Bach\u2019s music, and the one that students spend the most time learning.',
        'The basic rules are negative: don\u2019t move two voices in parallel fifths or parallel octaves. Don\u2019t cross voices (the alto shouldn\u2019t go below the tenor). Don\u2019t exceed the comfortable range of each voice. Don\u2019t leap in one voice without compensating in another. These prohibitions aren\u2019t arbitrary \u2014 they come from centuries of experience with what makes four-part vocal music sound good. Parallel fifths hollow out the texture. Voice crossing muddles who is singing what. Large leaps strain the singer.',
        'But the positive side of voice-leading is what makes Bach\u2019s music sing. Each voice should have a contour: a shape that rises, falls, arches, or descends over the course of a phrase. The soprano has the melody, so its contour is given. The bass has harmonic responsibilities. The alto and tenor, squeezed between, are where Bach\u2019s craft shows most clearly. A good tenor line feels like a melody in its own right \u2014 it steps more than it leaps, it balances upward and downward motion, and it arrives at the cadence through a tendency tone that makes the resolution feel natural.',
        'Dissonance is handled through a few standard devices. Passing tones connect two consonant notes by step through a dissonance. Neighbor tones step away and return. Suspensions hold a note over from the previous chord, creating a brief clash that resolves downward by step. Appoggiaturas leap to a dissonance and resolve by step. Bach uses all of these constantly, but suspensions are his favorite tool for expression \u2014 the 4\u20133 suspension at a cadence, where the soprano holds the fourth before falling to the third, is one of the most characteristic sounds in tonal music.',
        'The spacing rules (soprano to alto no more than an octave, alto to tenor no more than an octave, tenor to bass up to a twelfth) keep the four voices sounding like a unified choir rather than isolated strands. Bach occasionally breaks these limits, but only when a voice needs to reach a particular note for harmonic reasons.',
        'What distinguishes Bach\u2019s voice-leading from a student exercise is the independence among the parts. In a mediocre harmonization, the lower voices move together in block motion \u2014 up when the soprano goes up, down when it goes down. In Bach, the voices more often move contrary to each other: when the soprano rises, the bass falls; when the alto holds steady, the tenor steps down. This contrary motion is what gives the music its depth and vitality.',
      ],
      stats: [
        { label: 'Ranges', value: 'S: C4\u2013G5, A: F3\u2013C5, T: C3\u2013G4, B: E2\u2013C4' },
        { label: 'Max spacing', value: 'S\u2013A: octave, A\u2013T: octave, T\u2013B: 12th' },
        { label: 'Dissonance types', value: 'Passing, Neighbor, Suspension, Appoggiatura' },
      ],
    }),
  },
  {
    slug: 'fugue-technique',
    title: 'Fugue & Counterpoint',
    summary: 'Subjects, answers, stretto, episodes \u2014 the patient art of spinning one melodic idea into an entire piece.',
    content: () => ({
      paragraphs: [
        'Fugue is not a form in the way that sonata or rondo is. It\u2019s more like a procedure \u2014 a way of building a piece from a single melodic idea (the subject) through imitation, development, and transformation. Bach didn\u2019t invent the fugue, but he brought it to a level of complexity and expressiveness that no one before or since has matched.',
        'The procedure begins with an exposition. One voice enters alone with the subject. When it finishes, a second voice enters with the answer \u2014 the subject transposed to the dominant \u2014 while the first voice continues with a countersubject or free counterpoint. If there are three or four voices, the third enters with the subject again (back in the tonic), and the fourth with another answer. By the end of the exposition, all voices are active and the full texture is established.',
        'The answer can be "real" (an exact transposition to the dominant) or "tonal" (adjusted to keep the music from drifting away from the home key). Tonal answers are more common. The adjustment is usually small \u2014 a single interval changed by a half step \u2014 but it makes a large difference in tonal stability. Recognizing which notes are altered and why is one of the first analytical skills a student develops when studying fugue.',
        'After the exposition, the fugue alternates between middle entries (the subject appearing in new keys) and episodes (passages that develop fragments of the subject and countersubject through sequence). Episodes are where Bach is at his most inventive. He takes a motif of three or four notes from the subject and runs it through rising or falling sequences, sometimes inverting it, sometimes combining it with another fragment. The episodes modulate to new keys and release tension so that the next subject entry has fresh impact.',
        'Stretto \u2014 overlapping entries where a second voice begins the subject before the first has finished \u2014 is Bach\u2019s favorite tool for building climax. The C-sharp minor fugue from WTC Book I (BWV 849) is a celebrated example: five voices, extensive stretto, and a final section where the entries pile up with almost unbearable intensity.',
        'Some fugues go further. A double fugue has two subjects that eventually combine. A triple fugue has three. The unfinished final fugue of The Art of Fugue (BWV 1080) was apparently planned as a quadruple fugue \u2014 the third subject spells out B\u2013A\u2013C\u2013H in German notation (B\u266d\u2013A\u2013C\u2013B\u266e) \u2014 but Bach died before completing it.',
        'Inversion (turning the subject upside down), augmentation (stretching it to longer note values), and diminution (compressing it) are additional transformational techniques. They tend to mark climactic or structurally important moments. The subject of the A minor fugue from WTC II (BWV 889) appears in inversion so seamlessly that it\u2019s easy to miss on first hearing.',
        'The Well-Tempered Clavier is the central document for studying fugue. But the organ fugues (the "Great" G minor, BWV 542; the "St. Anne" in E-flat, BWV 552), The Art of Fugue, and the fugal choruses in the Mass in B minor and the passions extend the technique to voices and orchestra on a grand scale.',
      ],
      stats: [
        { label: 'WTC fugues', value: '48 (24 per book)' },
        { label: 'Voices', value: '2 to 5' },
        { label: 'Keys', value: 'All 24 major and minor' },
      ],
      links: [
        { label: 'The Art of Fugue (BWV 1080) on IMSLP', url: 'https://imslp.org/wiki/Die_Kunst_der_Fuge,_BWV_1080_(Bach,_Johann_Sebastian)' },
        { label: 'Musical Offering (BWV 1079) on IMSLP', url: 'https://imslp.org/wiki/Musikalisches_Opfer,_BWV_1079_(Bach,_Johann_Sebastian)' },
      ],
    }),
  },
  {
    slug: 'well-tempered-clavier',
    title: 'The Well-Tempered Clavier',
    summary: 'Two books, 48 preludes and fugues, all 24 keys \u2014 the most important keyboard collection ever written.',
    content: () => ({
      paragraphs: [
        'The Well-Tempered Clavier is two collections of preludes and fugues, one pair in each of the 24 major and minor keys. Book I dates from 1722, when Bach was in Cöthen; Book II was assembled around 1742, during the Leipzig years. Together they are the most important single work in the keyboard literature and the indispensable reference for anyone studying counterpoint.',
        '"Well-tempered" refers to a tuning system that allows all 24 keys to be played on a single keyboard. Bach did not specify which temperament \u2014 the question of whether he intended equal temperament, Werckmeister III, or some other system has generated centuries of debate and several doctoral dissertations. What matters musically is that the entire circle of keys is available, and Bach uses all of them.',
        'The preludes vary enormously. Some are etude-like patterns \u2014 the C major from Book I (BWV 846), with its arpeggiated chords that Gounod later set his Ave Maria over. Some are dances \u2014 the E-flat major from Book I (BWV 852) has the character of an allemande. Some are fully developed binary or ternary forms. The preludes from Book II tend to be longer and more elaborate.',
        'The fugues range from two voices (E minor, BWV 855) to five (C-sharp minor, BWV 849; B-flat minor from Book II, BWV 891). Short fugues might be 20 measures; long ones reach 80 or more. Some are bright and dance-like (D major, BWV 850); others are intensely chromatic (F-sharp minor, BWV 859).',
        'A few highlights from Book I: The C minor fugue (BWV 847) is a three-voice showpiece with a flowing subject \u2014 a student favorite for centuries. The B-flat minor (BWV 867), in five flats, is one of the most harmonically adventurous. The B major (BWV 868) pairs a gentle pastoral prelude with a fugue of almost Mozartean grace.',
        'Book II is sometimes called the mature collection. The subjects tend to be longer and more thematic, and the fugues are more complex in their tonal plans, visiting remote keys that the Book I fugues rarely touch. The F-sharp major fugue (BWV 882) has a subject so chromatic it almost dissolves the key. The A minor (BWV 889) demonstrates inversion and stretto with textbook clarity.',
        'If you are going to study one collection of music to understand how tonal counterpoint works, this is the one.',
      ],
      stats: [
        { label: 'Books', value: '2 (1722 and 1742)' },
        { label: 'Preludes & fugues', value: '48 pairs (96 pieces)' },
        { label: 'Voice range', value: '2 to 5 voices' },
      ],
      links: [
        { label: 'WTC Book I (BWV 846\u2013869) on IMSLP', url: 'https://imslp.org/wiki/The_Well-Tempered_Clavier,_Book_1,_BWV_846-869_(Bach,_Johann_Sebastian)' },
        { label: 'WTC Book II (BWV 870\u2013893) on IMSLP', url: 'https://imslp.org/wiki/The_Well-Tempered_Clavier,_Book_2,_BWV_870-893_(Bach,_Johann_Sebastian)' },
      ],
    }),
  },
  {
    slug: 'cantatas',
    title: 'The Cantatas',
    summary: 'Over 200 surviving works for voices and instruments, written nearly every week for the Lutheran church year.',
    content: () => ({
      paragraphs: [
        'Bach wrote cantatas nearly every week for much of his career, and over 200 survive. They were liturgical works \u2014 composed for specific Sundays and feast days \u2014 but they are also some of the most inventive and emotionally powerful music he wrote.',
        'A typical cantata runs 20 to 30 minutes and follows a loose pattern: an opening chorus or aria, several recitatives and arias that develop the day\u2019s biblical theme, and a closing chorale in four-part harmony. The forces vary from a few soloists with continuo to full orchestra with trumpets and timpani. Some cantatas were written in a few days; Bach\u2019s productivity during the first Leipzig years (1723\u20131726) borders on the unbelievable.',
        'The opening choruses are often the most ambitious movements. "Ein feste Burg ist unser Gott" (BWV 80) builds Luther\u2019s hymn into a massive choral fugue with orchestra. "Wachet auf, ruft uns die Stimme" (BWV 140) layers the chorale melody over a walking bass and flowing counterpoint. "Herz und Mund und Tat und Leben" (BWV 147) gives us "Jesu, Joy of Man\u2019s Desiring" \u2014 one of the most recognizable tunes in classical music, though in context it\u2019s the chorale at the end of Part I.',
        'The arias are where Bach\u2019s dramatic instincts come through. He assigns each aria an obbligato instrument \u2014 violin, oboe, flute, sometimes oboe da caccia or viola da gamba \u2014 that engages the voice in a genuine musical dialogue. These are not accompaniments; they are duets, each with its own melodic line.',
        'Bach organized his cantata production in annual cycles. At least five complete cycles are thought to have existed; roughly three survive. The second cycle (1724\u201325) is notable for its systematic use of chorale cantatas, in which every movement is based on a single hymn tune. This cycle is the closest Bach came to a unified large-scale project in the cantata genre.',
        'The secular cantatas \u2014 "Coffee Cantata" (BWV 211), "Peasant Cantata" (BWV 212), various congratulatory and birthday pieces \u2014 show a lighter, wittier side. The Coffee Cantata is practically a comic opera: a father tries to cure his daughter\u2019s coffee addiction. It\u2019s a reminder that Bach\u2019s range extended well beyond the sacred.',
      ],
      stats: [
        { label: 'Surviving cantatas', value: '200+' },
        { label: 'Annual cycles', value: '~5 (3 mostly surviving)' },
        { label: 'Typical duration', value: '20\u201330 minutes' },
      ],
      links: [
        { label: 'Bach cantatas on IMSLP (by BWV number)', url: 'https://imslp.org/wiki/Category:Bach,_Johann_Sebastian' },
      ],
    }),
  },
  {
    slug: 'passions-and-choral-works',
    title: 'The Passions & Major Choral Works',
    summary: 'The St. Matthew, the St. John, the Mass in B minor, the Christmas Oratorio \u2014 Bach\u2019s largest and most dramatic music.',
    content: () => ({
      paragraphs: [
        'The two surviving Passions \u2014 the St. John (BWV 245, 1724) and the St. Matthew (BWV 244, 1727) \u2014 are among the largest and most dramatic works in the choral repertoire. A third, the St. Mark (BWV 247), is largely lost. A fourth attributed to Bach, the "St. Luke Passion" (BWV 246), is now considered the work of another composer.',
        'The St. Matthew Passion runs over two and a half hours and calls for double chorus, double orchestra, soloists, and a boys\u2019 choir for the opening movement. It tells the Passion narrative from Matthew\u2019s Gospel in recitative, interrupts it with arias that reflect on the emotional meaning of each event, and intersperses chorales that tie the story to the congregation\u2019s faith. "Erbarme dich" (Have mercy), sung by the alto with solo violin, is among the most devastating pieces of vocal music ever composed.',
        'The St. John Passion is shorter and more dramatically concentrated. The crowd choruses \u2014 "Kreuzige! Kreuzige!" (Crucify!) \u2014 are some of Bach\u2019s most visceral writing. The narrative moves faster, with less reflective commentary than the Matthew, and the result feels almost operatic in its intensity.',
        'The Mass in B minor (BWV 232) is not a liturgical Mass in any practical sense \u2014 it\u2019s far too long for a service and was assembled over decades from cantata movements, parodies, and new compositions. But it is Bach\u2019s most comprehensive sacred work. The "Crucifixus" \u2014 a passacaglia over a descending chromatic bass \u2014 is one of the supreme examples of text-painting in all of music.',
        'The Christmas Oratorio (BWV 248) is six cantatas written for the feast days between Christmas and Epiphany in 1734\u201335. Linked by a continuous narrative, they tell the Nativity story with some of Bach\u2019s most brilliant music \u2014 trumpets, timpani, pastoral sicilianos, and radiant chorales.',
        'The Magnificat (BWV 243), originally in E-flat and later revised to D major, is a compact masterpiece. Twelve movements in about 25 minutes, from the opening "Magnificat anima mea" to the closing doxology \u2014 tight, festive, and relentlessly inventive.',
      ],
      stats: [
        { label: 'Surviving Passions', value: '2 (St. John, St. Matthew)' },
        { label: 'Mass in B minor', value: 'Assembled 1733\u20131749' },
        { label: 'Christmas Oratorio', value: '6 cantatas (1734\u201335)' },
      ],
      links: [
        { label: 'St. Matthew Passion (BWV 244) on IMSLP', url: 'https://imslp.org/wiki/Matth%C3%A4us-Passion,_BWV_244_(Bach,_Johann_Sebastian)' },
        { label: 'St. John Passion (BWV 245) on IMSLP', url: 'https://imslp.org/wiki/Johannes-Passion,_BWV_245_(Bach,_Johann_Sebastian)' },
        { label: 'Mass in B minor (BWV 232) on IMSLP', url: 'https://imslp.org/wiki/Mass_in_B_minor,_BWV_232_(Bach,_Johann_Sebastian)' },
        { label: 'Christmas Oratorio (BWV 248) on IMSLP', url: 'https://imslp.org/wiki/Weihnachts-Oratorium,_BWV_248_(Bach,_Johann_Sebastian)' },
      ],
    }),
  },
  {
    slug: 'text-music',
    title: 'Text & Music',
    summary: 'How Bach answers words with gesture, contour, chromatic color, and the Baroque tradition of musical rhetoric.',
    content: () => ({
      paragraphs: [
        'Bach composed most of his vocal music for the Lutheran liturgy, where words and music were understood as two aspects of the same act of worship. He was not merely setting words to notes \u2014 he was interpreting them. Every cantata aria, every passion recitative, every chorale setting reflects a close reading of the text.',
        'The Baroque tradition of musica poetica gave composers a vocabulary of standard figures. An ascending line (anabasis) for heaven, joy, or resurrection. A descending line (catabasis) for earth, death, or sorrow. A chromatic descent (passus duriusculus) for anguish. Short rests between notes (suspiratio) for sighing or grief. Sudden silence (abruptio) for death. These go back to the early 17th century and the writings of Burmeister and Bernhard.',
        'What sets Bach apart is how naturally these figures arise from the musical structure. In lesser hands, word-painting feels mechanical \u2014 a rising scale every time someone says "heaven." In Bach, the figures are embedded in the harmonic and contrapuntal fabric. The chromatic descent in "Erbarme dich" from the St. Matthew Passion doesn\u2019t just depict grief \u2014 it generates the entire harmonic motion of the movement. The rising line in "Et resurrexit" from the Mass in B minor propels the fugal exposition forward with real structural energy.',
        'The chorales provide the most compact examples. Many of the hymn texts deal with death, sin, grace, and salvation. Bach\u2019s settings respond to specific words: a darkened chord under "Kreuz" (cross), a sudden descent under "Tod" (death), an unexpected major sonority under "Freude" (joy). These shadings are not always visible in an abstract harmonic analysis \u2014 you need the text to hear them.',
        'Not all chorale settings in the standard collections preserve their original texts. Some survive as music only, the words lost or separated. Where texts do survive, they open a layer of meaning that the notes alone cannot fully convey. The chorales make sense as abstract harmony, but they make deeper sense with the words.',
        'The cantatas \u2014 over 200 survive \u2014 are the largest laboratory for text-music relationships. A typical cantata combines arias, recitatives, choruses, and chorales into a 20\u201330 minute work for a specific Sunday. The opening chorus often sets a psalm or Gospel text in elaborate counterpoint; the arias explore individual emotional responses; the closing chorale gathers the congregation back together.',
      ],
      stats: [
        { label: 'Key figures', value: 'Anabasis, Catabasis, Passus duriusculus' },
        { label: 'Tradition', value: 'Musica poetica (Baroque rhetoric)' },
        { label: 'Scope', value: 'Cantatas, passions, chorales' },
      ],
      links: [
        { label: 'St. Matthew Passion (BWV 244) on IMSLP', url: 'https://imslp.org/wiki/Matth%C3%A4us-Passion,_BWV_244_(Bach,_Johann_Sebastian)' },
        { label: 'St. John Passion (BWV 245) on IMSLP', url: 'https://imslp.org/wiki/Johannes-Passion,_BWV_245_(Bach,_Johann_Sebastian)' },
      ],
    }),
  },
];

// ─── Article Card ────────────────────────────────────────────────────

function ArticleCard({ article }: { article: ArticleMeta }) {
  return (
    <Link
      to={`/encyclopedia/${article.slug}`}
      className="group relative block p-6 rounded-2xl border border-border bg-paper-light hover:border-secondary hover:shadow-[0_18px_42px_rgba(201,168,76,0.12)] transition-all no-underline"
    >
      <CornerOrnaments />
      <div className="mb-4 h-1 w-20 rounded-full bg-gradient-to-r from-secondary to-primary opacity-70" aria-hidden="true" />
      <h3 className="font-serif text-lg font-semibold text-ink mb-2">{article.title}</h3>
      <p className="text-sm text-ink-muted leading-relaxed">{article.summary}</p>
      <div className="mt-4 text-sm text-primary opacity-0 transition-opacity group-hover:opacity-100">Read more →</div>
    </Link>
  );
}

// ─── Article Page ────────────────────────────────────────────────────

export function EncyclopediaArticle() {
  const { slug } = useParams<{ slug: string }>();
  const article = ARTICLES.find((a) => a.slug === slug);

  const { data: stats } = useQuery({
    queryKey: ['encyclopedia', 'stats'],
    queryFn: fetchEncyclopediaStats,
    staleTime: 10 * 60 * 1000,
  });

  if (!article) {
    return (
      <div className="max-w-[800px] mx-auto px-6 py-12">
        <p className="text-ink-muted">Article not found.</p>
        <Link to="/encyclopedia" className="text-primary text-sm mt-4 inline-block no-underline">Back to Encyclopedia</Link>
      </div>
    );
  }

  const content = article.content(stats || {});

  // Find adjacent articles for navigation
  const idx = ARTICLES.indexOf(article);
  const prev = idx > 0 ? ARTICLES[idx - 1] : null;
  const next = idx < ARTICLES.length - 1 ? ARTICLES[idx + 1] : null;

  return (
    <div className="max-w-[900px] mx-auto px-6 py-8">
      <div className="flex items-center gap-2 text-sm text-ink-muted mb-6">
        <Link to="/encyclopedia" className="hover:text-ink no-underline">Encyclopedia</Link>
        <span>/</span>
        <span className="text-ink font-medium">{article.title}</span>
      </div>

      <h1 className="text-4xl mb-3">{article.title}</h1>
      <p className="text-lg text-ink-muted mb-4 leading-relaxed">{article.summary}</p>
      <BaroqueFlourish className="mb-2" />
      <StaffDivider className="pt-0 mb-6" />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
        {content.stats.map((s, i) => (
          <div key={i} className="p-4 rounded-xl border border-border bg-paper-light shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
            <div className="text-lg font-semibold text-primary font-serif">{s.value}</div>
            <div className="text-xs uppercase tracking-[0.16em] text-ink-muted mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="space-y-4 mb-8">
        {content.paragraphs.map((p, i) => (
          <p key={i} className={`text-ink leading-relaxed ${i === 0 ? 'first-letter:float-left first-letter:mr-2 first-letter:text-5xl first-letter:font-serif first-letter:text-secondary' : ''}`}>
            {p}
          </p>
        ))}
      </div>

      {/* External links / scores */}
      {content.links && content.links.length > 0 && (
        <div className="p-5 rounded-2xl bg-paper-light border border-border shadow-[0_12px_30px_rgba(43,43,43,0.04)] mb-6">
          <h3 className="text-sm font-semibold text-ink-light mb-3">Scores & Further Reading</h3>
          <div className="space-y-2">
            {content.links.map((link, i) => (
              <a
                key={i}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-primary hover:text-primary-dark no-underline group"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0 opacity-60 group-hover:opacity-100">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
                {link.label}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Navigation between articles */}
      <div className="p-5 rounded-2xl bg-paper-light border border-border shadow-[0_12px_30px_rgba(43,43,43,0.04)] mb-6">
        <h3 className="text-sm font-semibold text-ink-light mb-3">Keep Reading</h3>
        <div className="flex gap-3 flex-wrap">
          {prev && (
            <Link to={`/encyclopedia/${prev.slug}`} className="text-sm text-primary hover:text-primary-dark no-underline">
              ← {prev.title}
            </Link>
          )}
          {next && (
            <Link to={`/encyclopedia/${next.slug}`} className="text-sm text-primary hover:text-primary-dark no-underline">
              {next.title} →
            </Link>
          )}
        </div>
      </div>

      <div className="p-5 rounded-2xl bg-paper-light border border-border shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
        <h3 className="text-sm font-semibold text-ink-light mb-2">Explore</h3>
        <div className="flex gap-3 flex-wrap">
          <Link to="/corpus" className="text-sm text-primary hover:text-primary-dark no-underline">Browse Chorales</Link>
          <Link to="/research" className="text-sm text-primary hover:text-primary-dark no-underline">Research Tools</Link>
          <Link to="/encyclopedia" className="text-sm text-primary hover:text-primary-dark no-underline">All Articles</Link>
        </div>
      </div>
    </div>
  );
}

// ─── Encyclopedia Index ──────────────────────────────────────────────

export function Encyclopedia() {
  return (
    <div className="max-w-[1100px] mx-auto px-6 py-8">
      <div className="mb-8">
        <div className="mb-2">
          <span className="inline-block text-secondary text-[11px] uppercase tracking-[0.28em] font-sans">
            Essays on Bach's Craft
          </span>
        </div>
        <SectionHeading className="mb-3">Encyclopedia</SectionHeading>
        <p className="text-ink-muted max-w-2xl">
          Nine essays on Bach's music: how the chorales work, what makes the fugues tick, and why these pieces
          have mattered to musicians for three hundred years. Each article includes links to free scores on IMSLP.
        </p>
        <BaroqueFlourish className="mt-4" />
        <StaffDivider className="pt-2" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {ARTICLES.map((a) => <ArticleCard key={a.slug} article={a} />)}
      </div>
    </div>
  );
}
