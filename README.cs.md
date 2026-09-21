# gauk-ai-feedback česky

*Tomáš Havránek, Univerzita Karlova · další nástroje, data a kód na
[meta-analysis.cz](https://meta-analysis.cz)*

Neoficiální kontrola přihlášky do Grantové agentury Univerzity Karlovy (GA UK)
před podáním. Přečte váš návrh a řekne, co opravit, dokud je čas. Nejdřív
formální problémy: chybějící kapitola, limit stran, rozpočet nad limity,
harmonogram podle akademického roku. Pak obsah, hlavně zda přihláška říká, co
projekt přinese, a zda to popsané metody a požadovaný čas umožňují.

> **Neoficiální.** Nejde o nástroj GA UK ani Univerzity Karlovy a žádná z nich
> ho neprověřila ani neschválila. Pravidla jsou přepsána ze zveřejněných
> dokumentů 24. kola a mohou obsahovat chyby; pokud zveřejněné dokumenty nebo
> vaše fakulta říkají něco jiného, platí ony. Kontrola vám neřekne, zda
> uspějete, a nikdy za vás nenapíše žádnou část přihlášky. Autor je členem
> Grantové rady GA UK; co z toho plyne, popisuje [DISCLOSURE.md](DISCLOSURE.md)
> (anglicky).

**Nejjednodušší je webová stránka:
[tjhavranek.github.io/gauk-ai-feedback](https://tjhavranek.github.io/gauk-ai-feedback/)**,
česky i anglicky a bez instalace. Zkopíruje za vás zadání pro chatbota a přílohy
umí zkontrolovat přímo ve vašem prohlížeči, aniž by je kamkoli odeslala.

## Než cokoli vložíte do chatu

Chatbot posílá vše, co vložíte, firmě, která ho provozuje. Podle čestného
prohlášení nesmí být text projektu bez svolení vedoucího projektu poskytnut
nikomu mimo řešitelský kolektiv, proto se nejdřív zeptejte vedoucího, obvykle
školitele. Vynechejte, co nemá odejít: nepublikovaná data a životopis vedoucího,
pokud s tím nesouhlasí. Zjistěte, zda vaše fakulta nemá pravidla pro nástroje
AI; pokyny univerzity jsou na <https://ai.cuni.cz/AI-81.html>. Účet s vypnutým
trénováním riziko snižuje, sdílení tím ale povoleno není.

## Jak na to

1. Otevřete [zadání v češtině](dist/prompt_cs.md) a klikněte na ikonu
   kopírování vpravo nahoře v šedém rámečku.
2. Založte nový chat a zadání vložte. Za ně vložte svůj návrh: pole webového
   formuláře a text návrhu projektu, případně životopisy. Uveďte sekci (A, B
   nebo C), dobu řešení a verzi formuláře. Dlouhý návrh můžete poslat
   v několika zprávách; řekněte, až bude kompletní. Začněte univerzitním
   Microsoft Copilotem přes [office365.cuni.cz](https://office365.cuni.cz/)
   s účtem CAS: podle UK se na tuto verzi vztahuje komerční ochrana dat. Zadání je
   stejné pro ChatGPT, Claude i Gemini. Pokud ho chatbot nepřijme celé,
   stáhněte si ho jako soubor z webové stránky a přiložte ho. K vložení osobních údajů dalších lidí, třeba
   životopisu vedoucího, stále potřebujete jejich výslovný souhlas.
3. Chatbot neumí spolehlivě počítat znaky ani strany. Chcete-li formální
   kontrolu i v číslech, vyplňte a vložte také
   [blok vlastního hlášení](dist/self_report_cs.md) s čísly z počitadel v
   přihlášce a z vlastností souborů. Bez něj se tyto řádky vrátí jako
   NEZMĚŘENO.
4. Přečtěte si posudek. Má vždy stejné části: stručné shrnutí, formální
   kontrolu, seznam toho, co kontrola nevidí, odstavec o přínosu projektu,
   nejvýše deset nálezů s doslovnou citací a konkrétní nápravou a odstavec,
   který můžete přeposlat školiteli.

Kontrolu si udělejte alespoň pár dní před fakultním termínem podání, ať zbude
čas na úpravy. Návrh upravte a kontrolu jednou nebo dvakrát zopakujte. Další
kola na stejném textu se už většinou opakují a lepším čtenářem je pak
školitel.

## Co kontrola nedělá

Neodhaduje šanci na financování, nedává body ani známku a nesrovnává vás s
jinými. Nepíše ani nepřepisuje váš text, ani když ji o to požádáte: podepisujete,
že jste přihlášku zpracovali samostatně.

Není pro hodnotitele. Oponenti, zpravodajové, členové oborových rad a fakultní
referenti by ji na přihlášky, které posuzují, používat neměli: hodnocení je
důvěrné a chatbot by text cizí přihlášky poslal třetí straně. Fakulty a kancelář
GA UK na ni ale mohou studenty upozornit před fakultním termínem.

## Prohlášení o použití AI

Přihláška se ptá, zda jste při přípravě použili umělou inteligenci, a pokud
ano, jakým způsobem a v jaké míře. I tato kontrola je použitím AI, poznamenejte
si proto nástroj a model. Podle informací k podání tato informace neslouží jako
kritérium hodnocení projektu.

## Pro pokročilé

Lokální formální kontrola (skript v Pythonu, který nic neodesílá) a volitelná,
experimentální cesta přes agentní nástroje Claude Code nebo Codex, které
fungují i v desktopových aplikacích Claude a ChatGPT bez terminálu, jsou
popsány v anglickém [README](README.md#2-the-local-formal-check) a stručně i na
[webové stránce](https://tjhavranek.github.io/gauk-ai-feedback/).

## Omezení

Kontrola pokrývá nové přihlášky 24. kola (soutěž se otevírá 1. října 2026,
projekty začínají v roce 2027), nikoli žádosti o pokračování ani závěrečné
zprávy. Pravidla přestávají platit 1. února 2027. Automatické testy používají
smyšlené přihlášky; na skutečných návrzích ji zkusilo jen pár lidí. Jazykový model může přehlédnout, co by odborník
viděl, a může se sebejistě mýlit. S nálezem, se kterým nesouhlasíte,
polemizujte a vědecké otázky řešte se školitelem.

Chybu v pravidlech prosím nahlaste v
[issues](https://github.com/tjhavranek/gauk-ai-feedback/issues) s odkazem na
zveřejněný zdroj. Nevkládejte tam žádnou část skutečné přihlášky. Na cokoli dalšího
slouží krátký anonymní [dotazník](https://forms.cloud.microsoft/e/t38pQfuAmm), na který odkazuje i stránka.

Autor: Tomáš Havránek ([meta-analysis.cz](https://meta-analysis.cz)), Univerzita
Karlova. Licence MIT.
