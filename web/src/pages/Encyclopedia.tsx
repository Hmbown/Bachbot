import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchEncyclopediaStats } from '@/lib/api';
import { BaroqueFlourish, CornerOrnaments, SectionHeading, StaffDivider } from '@/components/shared/Decorative';

// ─── Types ─────────────────────────────────────────────────────────

interface ArticleMeta {
  slug: string;
  title: string;
  summary: string;
  category: 'music' | 'craft' | 'practice';
  content: (stats: Record<string, unknown>) => {
    paragraphs: string[];
    stats: { label: string; value: string }[];
    links?: { label: string; url: string }[];
    tryIt?: { label: string; path: string; description: string }[];
    seeAlso?: string[];
  };
}

const CATEGORY_INFO: Record<string, { label: string; description: string }> = {
  music: {
    label: 'The Music',
    description: 'Bach\u2019s works: where they come from, what they contain, why they last.',
  },
  craft: {
    label: 'Craft & Technique',
    description: 'The compositional tools Bach used and how to hear them at work.',
  },
  practice: {
    label: 'Performance & Legacy',
    description: 'How the music was played, taught, and handed down.',
  },
};

// ─── Articles ────────────────────────────────────────────────────────

const ARTICLES: ArticleMeta[] = [

  // ═══════════════════════════════════════════════════════════════════
  // THE MUSIC
  // ═══════════════════════════════════════════════════════════════════

  {
    slug: 'bachs-life',
    title: "Bach's Life & Musical World",
    summary: 'Eisenach to Leipzig: the posts, the patrons, the rediscovery, and why it all matters for hearing the music.',
    category: 'music',
    content: () => ({
      paragraphs: [
        'Johann Sebastian Bach was born in Eisenach in 1685 into a family of musicians so extensive that "Bach" was practically a synonym for "musician" in Thuringia. He was orphaned at ten, raised by his older brother Johann Christoph, and from an early age showed a voracious appetite for learning music by copying manuscripts.',
        'His career moved through four main posts. In Weimar (1708\u20131717), as court organist and later concertmaster, he wrote most of his great organ works: the Passacaglia in C minor (BWV 582), the Orgelbüchlein collection of chorale preludes, and probably the Toccata and Fugue in D minor (BWV 565), though the attribution is debated. In Cöthen (1717\u20131723), as Kapellmeister to Prince Leopold, he turned to instrumental music: the Brandenburg Concertos, the solo violin sonatas and partitas, the first book of the Well-Tempered Clavier, the cello suites.',
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
      tryIt: [
        { label: 'Browse the Chorales', path: '/corpus', description: 'Explore 361 four-part settings with playback and analysis' },
      ],
      seeAlso: ['chorale-tradition', 'students-influence'],
    }),
  },
  {
    slug: 'chorale-tradition',
    title: 'The Chorale Tradition',
    summary: 'Lutheran hymn tunes set in four parts \u2014 the cornerstone of tonal harmony teaching for three centuries.',
    category: 'music',
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
      tryIt: [
        { label: 'Browse Chorales', path: '/corpus', description: 'Search, filter, and listen to all 361 settings' },
        { label: 'Harmonize a Melody', path: '/compose', description: 'Give BachBot a soprano line and see it fill in alto, tenor, and bass' },
        { label: 'Compare Two Chorales', path: '/corpus/compare', description: 'Side-by-side analysis with radar charts' },
      ],
      seeAlso: ['harmonic-language', 'voice-leading', 'continuo'],
    }),
  },
  {
    slug: 'well-tempered-clavier',
    title: 'The Well-Tempered Clavier',
    summary: 'Two books, 48 preludes and fugues, all 24 keys \u2014 the most important keyboard collection ever written.',
    category: 'music',
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
      tryIt: [
        { label: 'Write an Invention', path: '/compose', description: 'Enter a subject and BachBot generates answer, countersubject, and episode' },
      ],
      seeAlso: ['fugue-technique', 'tuning-temperament'],
    }),
  },
  {
    slug: 'organ-works',
    title: 'The Organ Works',
    summary: 'Passacaglias, toccatas, chorale preludes, trio sonatas \u2014 music written for the instrument Bach knew best.',
    category: 'music',
    content: () => ({
      paragraphs: [
        'Bach was an organist before he was anything else, and his organ works span nearly his entire career. The earliest pieces date from the Arnstadt years (1703\u20131707); the last revisions were made in Leipzig in the 1740s. In between, he produced the largest and most varied body of organ music any single composer has written.',
        'The free works \u2014 preludes, toccatas, fantasias, and their paired fugues \u2014 are the showpieces. The Toccata and Fugue in D minor (BWV 565) is the most famous, though its authorship has been questioned since the 1980s. More securely attributed and more musically substantial are the "Great" Preludes and Fugues: the A minor (BWV 543), with its brilliant pedal solo opening; the G minor (BWV 542), whose fugue subject is built on a Dutch folk song; the C minor (BWV 546), with one of Bach\u2019s longest and most tightly argued fugues; and the B minor (BWV 544), among the most sombre and powerful.',
        'The Passacaglia and Fugue in C minor (BWV 582) stands apart. A passacaglia is a set of continuous variations over a repeating bass line. Bach\u2019s has twenty variations over an eight-bar ground bass, followed by a double fugue whose first subject is derived from the passacaglia theme. It is one of the supreme demonstrations of large-scale musical architecture in the Baroque.',
        'The chorale preludes form the largest category. The Orgelbüchlein (BWV 599\u2013644) is a systematic collection of short settings, one per hymn tune, written mostly in Weimar. Each is a miniature: the chorale melody in one voice, accompanied by motifs that often illustrate the hymn text. "O Mensch, bewein dein Sünde groß" (BWV 622) uses a chromatic bass to depict grief; "In dir ist Freude" (BWV 615) is exuberant and dance-like. The Schübler Chorales (BWV 645\u2013650) are arrangements of cantata movements for organ \u2014 "Wachet auf" (BWV 645), from Cantata 140, is the best known. The Leipzig Chorales (BWV 651\u2013668), also called the "Great Eighteen," are mature revisions of earlier works, each more elaborate than the Orgelbüchlein settings.',
        'The Six Trio Sonatas (BWV 525\u2013530) are three-part works for two manuals and pedal, each voice independent. Bach reportedly wrote them for his eldest son Wilhelm Friedemann\u2019s keyboard training. They are among the most demanding organ pieces to play, not because of speed but because of the independence required between both hands and feet.',
        'Clavierübung III (1739), sometimes called the "German Organ Mass," is the most ambitious single publication. It opens with the Prelude in E-flat (BWV 552/1) \u2014 a massive three-section piece suggesting the Trinity \u2014 and closes with the "St. Anne" Fugue (BWV 552/2), a triple fugue in the same key. Between them are chorale settings of the catechism hymns, each in two versions (one large, one small), plus four duets (BWV 802\u2013805).',
      ],
      stats: [
        { label: 'Chorale preludes', value: '160+' },
        { label: 'Free works', value: '~30 preludes, toccatas, fantasias + fugues' },
        { label: 'Trio Sonatas', value: '6 (BWV 525\u2013530)' },
      ],
      links: [
        { label: 'Orgelbüchlein (BWV 599\u2013644) on IMSLP', url: 'https://imslp.org/wiki/Orgelb%C3%BCchlein,_BWV_599-644_(Bach,_Johann_Sebastian)' },
        { label: 'Passacaglia and Fugue in C minor (BWV 582) on IMSLP', url: 'https://imslp.org/wiki/Passacaglia_and_Fugue_in_C_minor,_BWV_582_(Bach,_Johann_Sebastian)' },
        { label: 'Trio Sonatas (BWV 525\u2013530) on IMSLP', url: 'https://imslp.org/wiki/6_Trio_Sonatas,_BWV_525-530_(Bach,_Johann_Sebastian)' },
      ],
      tryIt: [
        { label: 'Write an Invention', path: '/compose', description: 'Try composing a fugal exposition \u2014 the same kind of imitative writing that drives the organ fugues' },
      ],
      seeAlso: ['fugue-technique', 'well-tempered-clavier', 'chorale-tradition'],
    }),
  },
  {
    slug: 'solo-instrumental',
    title: 'The Solo Instrumental Works',
    summary: 'Violin sonatas and partitas, cello suites \u2014 music that makes a single instrument sound like an entire ensemble.',
    category: 'music',
    content: () => ({
      paragraphs: [
        'The six Sonatas and Partitas for solo violin (BWV 1001\u20131006) and the six Cello Suites (BWV 1007\u20131012) are the peaks of unaccompanied string writing. They were composed during the Cöthen years (1717\u20131723), when Bach had a first-rate court orchestra and no church obligations. Both sets push a single instrument to its polyphonic limits \u2014 implying harmony, counterpoint, and even fugue with just four strings.',
        'The violin works alternate sonatas (in the Italian church-sonata form: slow\u2013fast\u2013slow\u2013fast) with partitas (dance suites). The Chaconne from the Partita No. 2 in D minor (BWV 1004) is the colossus of the set: 256 bars of continuous variation over a four-bar harmonic pattern, building from a single line to full chords and back. Brahms, in a letter to Clara Schumann, called it "a whole world of the deepest thoughts and most powerful feelings." The Fugue from Sonata No. 1 in G minor (BWV 1001) sustains four-voice texture on a single violin \u2014 a technical and compositional feat that still astonishes.',
        'The cello suites follow a standard plan: Prelude\u2013Allemande\u2013Courante\u2013Sarabande\u2013[Galanterie]\u2013Gigue. The galanterie movement changes with each pair of suites: Minuets in Suites 1\u20132, Bourrées in 3\u20134, Gavottes in 5\u20136. Suite No. 5 in C minor uses scordatura \u2014 the A string tuned down to G \u2014 which darkens the instrument\u2019s colour and enables voicings otherwise impossible. Suite No. 6 in D major was probably written for a five-string instrument, possibly the violoncello piccolo.',
        'The cello suites were virtually unknown until Pablo Casals found a copy in a Barcelona second-hand music shop around 1890 and spent twelve years studying them before performing them publicly. His recordings in the 1930s established them in the repertoire. Today every serious cellist learns them; many record the complete set as a career statement.',
        'There is also a Partita for solo flute in A minor (BWV 1013), a four-movement work in the same style as the violin partitas. It is less often performed, partly because the flute lacks the violin\u2019s ability to imply polyphony through double-stopping, but its Sarabande is one of the most beautiful things Bach wrote for any instrument.',
      ],
      stats: [
        { label: 'Solo violin works', value: '6 (BWV 1001\u20131006)' },
        { label: 'Cello suites', value: '6 (BWV 1007\u20131012)' },
        { label: 'The Chaconne', value: '256 bars, ~15 minutes' },
      ],
      links: [
        { label: 'Violin Sonatas & Partitas on IMSLP', url: 'https://imslp.org/wiki/Sonatas_and_Partitas_for_Solo_Violin,_BWV_1001-1006_(Bach,_Johann_Sebastian)' },
        { label: 'Cello Suites on IMSLP', url: 'https://imslp.org/wiki/Cello_Suites,_BWV_1007-1012_(Bach,_Johann_Sebastian)' },
      ],
      seeAlso: ['dance-forms', 'fugue-technique'],
    }),
  },
  {
    slug: 'brandenburg-concertos',
    title: 'The Brandenburg Concertos',
    summary: 'Six concertos, six different instrumentations \u2014 a catalogue of Baroque ensemble writing at its most inventive.',
    category: 'music',
    content: () => ({
      paragraphs: [
        'In 1721, Bach sent a set of six concertos to Christian Ludwig, Margrave of Brandenburg, with a typically modest dedication. The Margrave apparently never had them performed \u2014 they were found unplayed in his library after his death. These are now among the most frequently performed orchestral works of the 18th century.',
        'No two concertos use the same instrumentation, and each explores a different way of balancing soloists against the ensemble. No. 1 in F major (BWV 1046) has the largest forces: two horns, three oboes, bassoon, violino piccolo, strings, and continuo, with an unusual four-movement structure ending in a Menuet with paired Trios and a Polacca. No. 2 in F major (BWV 1047) pits four soloists \u2014 trumpet, recorder, oboe, and violin \u2014 against the ripieno. The trumpet part, in the high clarino register, is among the most punishing in the Baroque repertoire.',
        'No. 3 in G major (BWV 1048) strips to pure strings: three violins, three violas, three cellos, bass, and continuo. The writing treats each group as a choir, alternating tutti and concertino textures. The "middle movement" is just two chords \u2014 a Phrygian half cadence that performers usually fill with an improvised cadenza or a brief Adagio.',
        'No. 4 in G major (BWV 1049) features a solo violin with two recorders, producing a bright, pastoral sound. No. 5 in D major (BWV 1050) gives the harpsichord an extended solo cadenza in the first movement \u2014 65 bars of virtuosic writing that essentially launches the keyboard concerto as a genre. Bach may have written it to show off a new harpsichord acquired in Berlin.',
        'No. 6 in B-flat major (BWV 1051) is the most unusual scoring: two violas da braccio, two violas da gamba, cello, and continuo. No violins at all. The low, dark sonority is unlike anything else in Bach. It has been suggested that Bach wrote the viola da braccio parts for himself and Prince Leopold, who was an accomplished player of the viola da gamba.',
        'Together the six concertos form a compendium of concerto technique: ritornello form, concertino-ripieno contrast, imitative counterpoint within the ensemble, and solo display. They are to the Baroque concerto what the Well-Tempered Clavier is to the keyboard fugue.',
      ],
      stats: [
        { label: 'Concertos', value: '6 (BWV 1046\u20131051)' },
        { label: 'Dedicated', value: '1721, to Margrave of Brandenburg' },
        { label: 'Scoring', value: 'Different instrumentation in each' },
      ],
      links: [
        { label: 'Brandenburg Concertos on IMSLP', url: 'https://imslp.org/wiki/Brandenburg_Concertos,_BWV_1046-1051_(Bach,_Johann_Sebastian)' },
      ],
      seeAlso: ['bachs-life', 'dance-forms'],
    }),
  },
  {
    slug: 'cantatas',
    title: 'The Cantatas',
    summary: 'Over 200 surviving works for voices and instruments, written nearly every week for the Lutheran church year.',
    category: 'music',
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
      tryIt: [
        { label: 'Browse Chorale Settings', path: '/corpus', description: 'Many closing chorales from cantatas are in the corpus' },
      ],
      seeAlso: ['text-music', 'passions-and-choral-works', 'chorale-tradition'],
    }),
  },
  {
    slug: 'passions-and-choral-works',
    title: 'The Passions & Major Choral Works',
    summary: 'The St. Matthew, the St. John, the Mass in B minor, the Christmas Oratorio \u2014 Bach\u2019s largest and most dramatic music.',
    category: 'music',
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
      tryIt: [
        { label: 'Browse Chorales', path: '/corpus', description: 'The passion chorales appear in the four-part corpus' },
      ],
      seeAlso: ['cantatas', 'text-music'],
    }),
  },

  // ═══════════════════════════════════════════════════════════════════
  // CRAFT & TECHNIQUE
  // ═══════════════════════════════════════════════════════════════════

  {
    slug: 'harmonic-language',
    title: 'Harmonic Language',
    summary: 'Keys, secondary dominants, cadences, modulation \u2014 how Bach colors a phrase and why his vocabulary is so large.',
    category: 'craft',
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
      tryIt: [
        { label: 'Search Progressions', path: '/research', description: 'Find recurring chord successions across the entire corpus' },
        { label: 'Chorale Profile', path: '/research', description: 'See harmonic variety, cadence habits, and spacing for any chorale' },
        { label: 'Browse Chorales', path: '/corpus', description: 'Open any chorale to see Roman numerals, cadences, and modulation' },
      ],
      seeAlso: ['voice-leading', 'chorale-tradition', 'continuo'],
    }),
  },
  {
    slug: 'voice-leading',
    title: 'Voice-Leading',
    summary: 'How the four voices stay singable, independent, and tightly woven \u2014 the single most important concept in Bach\u2019s music.',
    category: 'craft',
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
      tryIt: [
        { label: 'Study Species Counterpoint', path: '/theory', description: 'Write against a cantus firmus and learn voice-leading from first principles' },
        { label: 'Browse Chorales', path: '/corpus', description: 'Switch to voice-leading view to see each part independently' },
        { label: 'Harmonize a Melody', path: '/compose', description: 'See how BachBot handles voice-leading in its generated harmonizations' },
      ],
      seeAlso: ['harmonic-language', 'fugue-technique', 'chorale-tradition'],
    }),
  },
  {
    slug: 'fugue-technique',
    title: 'Fugue & Counterpoint',
    summary: 'Subjects, answers, stretto, episodes \u2014 the patient art of spinning one melodic idea into an entire piece.',
    category: 'craft',
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
      tryIt: [
        { label: 'Write an Invention', path: '/compose', description: 'Enter a subject and BachBot generates a tonal answer, countersubject, and sequential episode' },
        { label: 'Search for Patterns', path: '/research', description: 'Find recurring melodic and harmonic sequences across the corpus' },
      ],
      seeAlso: ['well-tempered-clavier', 'organ-works'],
    }),
  },
  {
    slug: 'text-music',
    title: 'Text & Music',
    summary: 'How Bach answers words with gesture, contour, chromatic color, and the Baroque tradition of musical rhetoric.',
    category: 'craft',
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
      tryIt: [
        { label: 'Browse Chorales', path: '/corpus', description: 'See harmonic analysis alongside the notes \u2014 then imagine the words underneath' },
      ],
      seeAlso: ['cantatas', 'passions-and-choral-works', 'ornamentation'],
    }),
  },
  {
    slug: 'dance-forms',
    title: 'Dance Forms in Bach',
    summary: 'Allemande, courante, sarabande, gigue \u2014 the dance movements that structure the suites and partitas.',
    category: 'craft',
    content: () => ({
      paragraphs: [
        'Most of Bach\u2019s suites and partitas follow the same core plan: Allemande\u2013Courante\u2013Sarabande\u2013Gigue, with optional "galanterie" movements (bourrée, gavotte, menuet, and others) inserted between the sarabande and gigue. By Bach\u2019s time these dances were no longer meant for actual dancing \u2014 they were stylized, abstract pieces that retained the rhythmic character and phrase structure of their dance origins.',
        'The Allemande is usually in moderate 4/4, with a short anacrusis (pickup) and a texture of flowing sixteenth notes that give it a walking, conversational quality. It is the most "learned" of the standard dances \u2014 the one where Bach is most likely to weave imitative counterpoint into the fabric.',
        'The Courante comes in two varieties. The French courante is in 3/2, stately and dignified, often with hemiola at the cadences (a momentary shift to 3/4 feeling). The Italian corrente is faster, in 3/4, with running eighth or sixteenth notes. Bach uses both types. The French Suites tend toward the faster corrente; the English Suites include genuine French courantes.',
        'The Sarabande is the slow movement of the suite: 3/4, with a characteristic emphasis on beat two. Historically it originated as a wild dance from Latin America, was imported to Spain, and was gradually tamed by the French court into something meditative and stately. In Bach, sarabandes are often the emotional center of the suite \u2014 spare in texture, rich in ornamentation, and deeply expressive. The Sarabande from the Cello Suite No. 5 (BWV 1011) is one of the great slow movements in all of Baroque music.',
        'The Gigue closes the suite. It is typically fast and in compound meter (6/8, 12/8, or 3/8). Many of Bach\u2019s gigues are fugal \u2014 the second half inverts the subject of the first. The English gigue is lighter and quicker; the French gigue uses dotted rhythms and a more angular contour.',
        'The galanterie movements are where variety enters. A Bourrée is in quick duple time with an upbeat of a single quarter note. A Gavotte is similar but begins on the half-bar (beat three). A Menuet is in moderate 3/4 \u2014 the only Baroque dance that survived into the Classical period, becoming the third movement of Haydn and Mozart symphonies. A Polonaise is in moderate 3/4 with a distinctive rhythmic pattern. Galanteries usually come in pairs (I\u2013II\u2013I), with the second often in a contrasting key or scoring.',
        'Where to find them: the six French Suites (BWV 812\u2013817), six English Suites (BWV 806\u2013811), and six Partitas for keyboard (BWV 825\u2013830); the six Cello Suites (BWV 1007\u20131012) and three Violin Partitas (BWV 1002, 1004, 1006); and the four Orchestral Suites (BWV 1066\u20131069), whose famous "Air on the G String" is the second movement of No. 3.',
      ],
      stats: [
        { label: 'Standard order', value: 'Allemande\u2013Courante\u2013Sarabande\u2013[Galanterie]\u2013Gigue' },
        { label: 'Keyboard suites', value: '18 (6 French, 6 English, 6 Partitas)' },
        { label: 'Orchestral suites', value: '4 (BWV 1066\u20131069)' },
      ],
      links: [
        { label: 'French Suites (BWV 812\u2013817) on IMSLP', url: 'https://imslp.org/wiki/French_Suites,_BWV_812-817_(Bach,_Johann_Sebastian)' },
        { label: 'English Suites (BWV 806\u2013811) on IMSLP', url: 'https://imslp.org/wiki/English_Suites,_BWV_806-811_(Bach,_Johann_Sebastian)' },
        { label: 'Orchestral Suites (BWV 1066\u20131069) on IMSLP', url: 'https://imslp.org/wiki/Orchestral_Suites,_BWV_1066-1069_(Bach,_Johann_Sebastian)' },
      ],
      tryIt: [
        { label: 'Explore Harmonic Rhythm', path: '/research', description: 'Compare how harmonic rhythm differs across chorales \u2014 the same rhythmic awareness drives the dances' },
      ],
      seeAlso: ['solo-instrumental', 'brandenburg-concertos'],
    }),
  },

  // ═══════════════════════════════════════════════════════════════════
  // PERFORMANCE & LEGACY
  // ═══════════════════════════════════════════════════════════════════

  {
    slug: 'ornamentation',
    title: 'Ornamentation',
    summary: 'Trills, mordents, turns, appoggiaturas \u2014 the expected embellishments that Baroque performers add to the written notes.',
    category: 'practice',
    content: () => ({
      paragraphs: [
        'In Baroque music, the written notes are the skeleton. The performer is expected to add ornaments \u2014 trills, mordents, turns, appoggiaturas, and other figures \u2014 according to conventions that were understood by musicians of the time but that modern players have to learn from historical sources.',
        'Bach left an ornament table in 1720, written into the Clavier-Büchlein for his eldest son Wilhelm Friedemann. It lists the standard ornaments with their symbols and realizations: the trill (beginning on the upper note), the mordent (a quick alternation with the note below), the turn (upper\u2013main\u2013lower\u2013main), the slide (an approach from a third below), and several compound figures. This table is the single most important primary source for how Bach intended ornaments to be played.',
        'The most consequential rule, and the one modern performers most often get wrong, is that trills in Baroque music begin on the upper note, not the main note. A trill on D starts C\u2013D\u2013C\u2013D (or D\u2013C\u2013D if indicated differently), not D\u2013E\u2013D\u2013E. This changes the harmonic effect: the upper-note start creates a brief appoggiatura, adding a moment of tension before the resolution. The Romantic-era convention of starting on the main note is a later development.',
        'C. P. E. Bach\u2019s treatise "Versuch über die wahre Art das Clavier zu spielen" (Essay on the True Art of Playing Keyboard Instruments, 1753/1762) is the fullest guide to Baroque keyboard ornamentation. C. P. E. writes explicitly about his father\u2019s practice and provides detailed examples of how to ornament different musical contexts. Every serious Bach performer reads it.',
        'Bach sometimes writes ornaments out in full, especially in the more virtuosic keyboard works. The Goldberg Variations (BWV 988) are full of written-out trills, turns, and mordents integrated into the motivic fabric. In the chorales and cantatas, ornaments are more often indicated by symbols or left to the performer\u2019s judgment. The degree to which performers should add unwritten ornaments to Bach is still debated; the historically-informed performance movement generally adds more than mainstream performers do.',
        'Ornamentation in Bach is never merely decorative. Each ornament has a harmonic and rhythmic function: a trill emphasizes a cadential note, a mordent activates a melodic line, an appoggiatura adds expressive weight. Learning to ornament well means learning to hear these functions and apply them where the music calls for them, not as reflexive additions to every long note.',
      ],
      stats: [
        { label: 'Ornament table', value: '1720 (for W. F. Bach)' },
        { label: 'Key source', value: 'C. P. E. Bach, Versuch (1753)' },
        { label: 'Standard ornaments', value: 'Trill, mordent, turn, appoggiatura, slide' },
      ],
      links: [
        { label: 'Goldberg Variations (BWV 988) on IMSLP', url: 'https://imslp.org/wiki/Goldberg_Variations,_BWV_988_(Bach,_Johann_Sebastian)' },
      ],
      seeAlso: ['voice-leading', 'text-music', 'continuo'],
    }),
  },
  {
    slug: 'tuning-temperament',
    title: 'Tuning & Temperament',
    summary: 'What "well-tempered" actually means, why it matters, and the centuries-old debate about how Bach tuned his keyboards.',
    category: 'practice',
    content: () => ({
      paragraphs: [
        'The physics of pitch creates a problem for keyboard instruments. A series of acoustically pure fifths (ratio 3:2) does not cycle back to the starting note after twelve steps \u2014 it overshoots by a small amount called the Pythagorean comma. This means you cannot tune all keys perfectly on a 12-note keyboard. Something has to give. The history of temperament is the history of deciding what to sacrifice.',
        'Meantone temperament, dominant from the 15th through 17th centuries, sacrifices some fifths to make the thirds pure. The result sounds beautiful in keys close to C major but increasingly harsh as you move toward remote keys. F-sharp major in quarter-comma meantone is essentially unusable \u2014 the "wolf" fifth between G-sharp and E-flat howls.',
        'Well temperaments, developed in the late 17th century by theorists like Andreas Werckmeister, distribute the Pythagorean comma unequally among the fifths so that all keys are playable. Crucially, they do not make all keys sound the same. In Werckmeister III, C major is calm and centered; F-sharp major is tense and bright. Each key has a distinct color, and composers could \u2014 and did \u2014 choose keys for their expressive qualities.',
        'Equal temperament divides the octave into twelve exactly equal semitones. All keys sound identical, which is convenient but eliminates key color entirely. It became standard in the 19th century and is what most modern pianos use. Whether Bach intended equal temperament or a well temperament is the central question. The title "Das Wohltemperierte Clavier" means "the well-tuned keyboard," not "the equally-tuned keyboard." Most scholars now believe Bach used some form of well temperament, though which one is fiercely debated.',
        'In 2005, Bradley Lehman proposed that the decorative loops on the title page of WTC Book I encode a specific temperament. His reading produces a system close to some historical well temperaments and has been adopted by some performers. Others are skeptical. The debate continues.',
        'For listening, what matters is this: if you play the WTC on a well-tempered instrument, the key of each prelude and fugue is part of the composition. The C major prelude sounds different from the F-sharp major prelude not just because the notes differ but because the intervals differ. The choice to write a piece in B minor rather than C minor is an expressive decision, not just a transpositional convenience. On an equally-tempered piano, that dimension of the music is invisible.',
      ],
      stats: [
        { label: 'Systems', value: 'Pythagorean, Meantone, Well temperament, Equal' },
        { label: 'The question', value: 'Which temperament did Bach use?' },
        { label: 'The comma', value: '~23.5 cents (Pythagorean)' },
      ],
      links: [
        { label: 'WTC Book I on IMSLP', url: 'https://imslp.org/wiki/The_Well-Tempered_Clavier,_Book_1,_BWV_846-869_(Bach,_Johann_Sebastian)' },
      ],
      seeAlso: ['well-tempered-clavier', 'harmonic-language'],
    }),
  },
  {
    slug: 'continuo',
    title: 'Continuo Practice',
    summary: 'Figured bass, the role of the harpsichord and organ, and the rhythmic-harmonic backbone of Baroque ensemble music.',
    category: 'practice',
    content: (s) => ({
      paragraphs: [
        'Nearly all Baroque ensemble music rests on the basso continuo: a bass line played by a low-pitched instrument (cello, viola da gamba, bassoon) together with a chord instrument (harpsichord, organ, lute, or theorbo) that fills in the harmonies. The chord player reads a figured bass \u2014 a bass line annotated with numbers indicating the intervals above the bass note. "6" means first inversion. "6/4" means second inversion. "7" means add a seventh. No numbers means root position.',
        'The realization \u2014 choosing the exact voicing, spacing, and rhythm of the chords \u2014 was improvised by the performer. A good continuo player adjusts the texture constantly: thicker chords in loud passages, thinner in quiet ones, close spacing for warmth, wide spacing for clarity. It is one of the most demanding roles in Baroque music because it requires real-time harmonic thinking.',
        'Bach\u2019s continuo parts are more prescriptive than some of his contemporaries. In several cantatas he writes out the organ realization fully, and in the St. Matthew Passion he specifies two separate continuo groups, one for each chorus-orchestra pair. He also taught figured bass systematically \u2014 several of his students\u2019 notebooks survive with exercises in bass realization.',
        'In sacred music, the organ served as the continuo instrument. In secular music \u2014 concertos, chamber sonatas, orchestral suites \u2014 the harpsichord took over. The keyboard concerto as a genre arguably begins with Bach: Brandenburg Concerto No. 5 (BWV 1050) gives the harpsichord a solo cadenza that breaks decisively out of the continuo role.',
        `Learning to realize figured bass is still one of the most practical things a musician can do. It teaches you to think harmonically in real time: given a bass note and a figure, you immediately hear the chord, choose a voicing, and connect it smoothly to the next. The ${s.total_chorales || 361} chorales in this corpus are essentially figured bass exercises in reverse \u2014 the four voices are written out, but the underlying figured bass logic is the same.`,
        'The connection between figured bass and chorale harmonization is direct. Both start from the bass line. Both require you to think about voice-leading between chords. Both reward knowing which chord inversions create smooth stepwise motion in the upper parts. If you can harmonize a chorale, you can realize a figured bass, and vice versa.',
      ],
      stats: [
        { label: 'Instruments', value: 'Harpsichord, organ, cello, viola da gamba' },
        { label: 'Notation', value: 'Bass line + figures (e.g. 6, 4/3, 7)' },
        { label: 'Role', value: 'Harmonic-rhythmic foundation' },
      ],
      tryIt: [
        { label: 'Realize Figured Bass', path: '/compose', description: 'Enter a bass line with figures and BachBot fills in the upper voices' },
        { label: 'Study Counterpoint', path: '/theory', description: 'Species counterpoint builds the same voice-leading skills continuo players need' },
      ],
      seeAlso: ['harmonic-language', 'chorale-tradition', 'ornamentation'],
    }),
  },
  {
    slug: 'students-influence',
    title: "Bach's Students & Legacy",
    summary: 'The sons, the students, the 19th-century revival, and how the music reached us.',
    category: 'practice',
    content: () => ({
      paragraphs: [
        'Bach was a lifelong teacher. As Thomaskantor in Leipzig, he was responsible for training the boys of the Thomasschule in music. He also taught private students, some of whom became significant composers in their own right. Johann Friedrich Agricola, Johann Ludwig Krebs, and Johann Philipp Kirnberger all studied with him and helped transmit his methods to the next generation.',
        'But his most famous students were his own sons. Wilhelm Friedemann (1710\u20131784), the eldest, was the most gifted but least disciplined \u2014 a brilliant organist whose career unravelled and who sold or lost many of his father\u2019s manuscripts. Carl Philipp Emanuel (1714\u20131788), the "Hamburg Bach," became the most influential of the sons. His keyboard music and his treatise on keyboard playing (the "Versuch," 1753/1762) were central to the transition from Baroque to Classical style; Haydn and Beethoven both studied his work. Johann Christian (1735\u20131782), the "London Bach," wrote Italianate operas and symphonies and directly influenced the young Mozart.',
        'After Bach\u2019s death in 1750, his music largely dropped out of public performance. His sons\u2019 newer style was fashionable; the father\u2019s counterpoint was considered dry and academic. But it never disappeared entirely. Mozart studied Bach\u2019s fugues in the 1780s (through Baron van Swieten\u2019s library in Vienna) and was deeply affected. Beethoven grew up playing the Well-Tempered Clavier and called Bach "the original father of harmony."',
        'The public revival began on March 11, 1829, when the twenty-year-old Felix Mendelssohn conducted the St. Matthew Passion in Berlin \u2014 its first performance in nearly a century. The response was overwhelming. Within two decades, the Bach-Gesellschaft was founded (1850) to publish a complete critical edition of Bach\u2019s works, a project that ran until 1899 and produced 46 volumes. Philipp Spitta\u2019s two-volume biography (1873\u20131880) established the scholarly foundation.',
        'The 20th century brought new waves of rediscovery. Albert Schweitzer \u2014 theologian, physician, and organist \u2014 published a study of Bach in 1905 that emphasized the role of text-painting in the vocal works. Wanda Landowska revived the harpsichord as a concert instrument, making the first recording of the Goldberg Variations in 1933. Glenn Gould\u2019s 1955 recording of the same work, on piano, became one of the best-selling classical albums ever.',
        'The historically-informed performance movement, beginning in the 1960s and 1970s with Nikolaus Harnoncourt, Gustav Leonhardt, and later John Eliot Gardiner and Masaaki Suzuki, transformed how Bach is played. Period instruments, Baroque pitch, well temperaments, smaller ensembles, rhetorical phrasing \u2014 these performers argued that understanding Bach\u2019s sound world was essential to understanding his music. The debate between "historical" and "modern" approaches continues, but the music\u2019s hold on performers and audiences has only grown.',
        'The 371 Chorale Harmonizations that C. P. E. Bach and Kirnberger gathered after the composer\u2019s death and that Breitkopf published in the 1780s became the foundation of tonal harmony teaching in conservatories worldwide. Three centuries later, students still learn harmony from these chorales. That these small, functional pieces \u2014 written for weekly church services \u2014 became the bedrock of an entire discipline says something about the depth of musical thought they contain.',
      ],
      stats: [
        { label: 'Famous sons', value: '4 composers (W.F., C.P.E., J.C.F., J.C.)' },
        { label: 'Revival', value: '1829 (Mendelssohn, St. Matthew Passion)' },
        { label: 'Bach-Gesellschaft', value: '1850\u20131899 (46 volumes)' },
      ],
      links: [
        { label: 'Complete works on IMSLP', url: 'https://imslp.org/wiki/Category:Bach,_Johann_Sebastian' },
      ],
      tryIt: [
        { label: 'Browse the Chorales', path: '/corpus', description: 'Explore the collection that C. P. E. Bach and Kirnberger preserved' },
      ],
      seeAlso: ['bachs-life', 'chorale-tradition', 'ornamentation'],
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
  const categoryLabel = CATEGORY_INFO[article.category]?.label || '';

  // Find adjacent articles within the same category for navigation
  const sameCat = ARTICLES.filter((a) => a.category === article.category);
  const catIdx = sameCat.indexOf(article);
  const prev = catIdx > 0 ? sameCat[catIdx - 1] : null;
  const next = catIdx < sameCat.length - 1 ? sameCat[catIdx + 1] : null;

  // Resolve seeAlso slugs to article objects
  const seeAlsoArticles = (content.seeAlso || [])
    .map((s) => ARTICLES.find((a) => a.slug === s))
    .filter(Boolean) as ArticleMeta[];

  return (
    <div className="max-w-[900px] mx-auto px-6 py-8">
      <div className="flex items-center gap-2 text-sm text-ink-muted mb-6">
        <Link to="/encyclopedia" className="hover:text-ink no-underline">Encyclopedia</Link>
        <span>/</span>
        <span className="text-ink-muted">{categoryLabel}</span>
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

      {/* Try It — interactive tool links */}
      {content.tryIt && content.tryIt.length > 0 && (
        <div className="p-5 rounded-2xl bg-surface border border-secondary/30 shadow-[0_12px_30px_rgba(201,168,76,0.06)] mb-6">
          <h3 className="text-sm font-semibold text-ink-light mb-3">Try It</h3>
          <div className="space-y-2.5">
            {content.tryIt.map((t, i) => (
              <Link
                key={i}
                to={t.path}
                className="flex items-start gap-2.5 text-sm no-underline group"
              >
                <span className="text-primary mt-0.5 flex-shrink-0 opacity-70 group-hover:opacity-100 transition-opacity">→</span>
                <span>
                  <span className="font-medium text-primary group-hover:text-primary-dark transition-colors">{t.label}</span>
                  <span className="text-ink-muted"> — {t.description}</span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

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

      {/* Related articles */}
      {seeAlsoArticles.length > 0 && (
        <div className="p-5 rounded-2xl bg-paper-light border border-border shadow-[0_12px_30px_rgba(43,43,43,0.04)] mb-6">
          <h3 className="text-sm font-semibold text-ink-light mb-3">Related Articles</h3>
          <div className="flex gap-3 flex-wrap">
            {seeAlsoArticles.map((a) => (
              <Link
                key={a.slug}
                to={`/encyclopedia/${a.slug}`}
                className="text-sm text-primary hover:text-primary-dark no-underline"
              >
                {a.title}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Navigation within category */}
      {(prev || next) && (
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
      )}

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

const CATEGORY_ORDER: Array<'music' | 'craft' | 'practice'> = ['music', 'craft', 'practice'];

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
          Seventeen essays on Bach's music: how the chorales work, what makes the fugues tick, how the
          dances move, and why these pieces have mattered to musicians for three hundred years. Each
          article links to free scores on IMSLP and to the tools on this site where you can hear,
          analyze, and try the techniques yourself.
        </p>
        <BaroqueFlourish className="mt-4" />
        <StaffDivider className="pt-2" />
      </div>

      {CATEGORY_ORDER.map((cat) => {
        const info = CATEGORY_INFO[cat];
        const articles = ARTICLES.filter((a) => a.category === cat);
        return (
          <div key={cat} className="mb-10">
            <h2 className="text-xl font-serif font-semibold text-ink mb-1">{info.label}</h2>
            <p className="text-sm text-ink-muted mb-4">{info.description}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {articles.map((a) => (
                <ArticleCard key={a.slug} article={a} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
