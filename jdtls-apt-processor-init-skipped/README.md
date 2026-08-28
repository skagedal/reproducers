# jdtls: Gradle's annotation processor path order is not preserved

**Status: reproduced minimally, fix verified. Ready to file.**

jdtls collects a project's annotation processors into a `HashSet`, so the
`.factorypath` it writes is in rehashed order rather than the order Gradle gives
javac. Processor *discovery* order is load-bearing: the compiler stops looking
for more processors once every annotation present has been claimed, so a
processor that claims nothing — one that exists only to have `init()` called, to
capture the `ProcessingEnvironment` for a non-processor collaborator to read —
is initialized only if it precedes the processors that do the claiming.

Reorder the path and that processor silently never runs. The collaborator then
reads an uninitialized static and the build fails in the IDE while `./gradlew`
on the same sources succeeds.

Proposed upstream issue text is at the bottom: [Issue draft](#issue-draft).

## Reproducing

```sh
cd verify
python3 check_order.py
```

Phase 1 needs nothing but Gradle. Phase 2 drives jdtls over LSP on stdio via
`jdtls_harness.py`: it answers every server→client request so the server never
stalls, waits for `ServiceReady`, waits for a `.factorypath` to be written, and
compares it against the path Gradle reports. Workspaces are created under the
system temp dir — **not** inside the project, since an Eclipse workspace nested
in the project being imported makes the import fail silently.

Edit `JDTLS` at the top of `jdtls_harness.py` if your path differs.

## The build here

`processors/` produces two processor jars plus six empty filler jars:

- `holder.jar` — `OptionsHolder`, `@SupportedAnnotationTypes({})`. Captures
  `processingEnv.getOptions()` into a static in `init()`. Claims nothing.
- `claimer.jar` — `ThingProcessor`, claims `demo.app.Thing`, and reads
  `OptionsHolder`'s static while processing it.

`app/` has one class annotated `@Thing`. The fillers only make the path long
enough that a rehash is certain to reorder it; with two entries a `HashSet`
might come out right by luck.

This is the shape of `no.entur.mapstruct.spi:protobuf-spi-impl`, where
`ProcessingEnvOptionsHolder` is a claims-nothing processor whose static is read
by `ProtobufEnumMappingStrategy` — a MapStruct SPI, so it has no
`ProcessingEnvironment` of its own — while `org.mapstruct.ap.MappingProcessor`
in a separate jar does the claiming.

## What was measured

**Phase 1 — plain javac is order-sensitive.** Same jars, same sources, only the
order of `annotationProcessorPath` differs (`-PclaimerFirst` flips it):

| processor path order  | `./gradlew :app:compileJava`                                      |
| --------------------- | ----------------------------------------------------------------- |
| holder before claimer | compiles                                                          |
| claimer before holder | `error: ... IllegalStateException: OptionsHolder not initialized yet.` |

So this is not an ECJ-versus-javac difference. Both compilers stop discovering
processors once the annotations present are claimed.

**Phase 2 — jdtls hands the same path to ECJ in a different order.**

```
  #  gradle (what javac sees)  jdtls .factorypath
  1  holder.jar                claimer.jar     <-- differs
  2  claimer.jar               filler5.jar     <-- differs
  3  filler1.jar               holder.jar      <-- differs
  4  filler2.jar               filler6.jar     <-- differs
  5  filler3.jar               filler1.jar     <-- differs
  6  filler4.jar               filler4.jar
  7  filler5.jar               filler3.jar     <-- differs
  8  filler6.jar               filler2.jar     <-- differs

  gradle: holder first;  jdtls: claimer first
  jdtls reports on Foo.java: Internal error in ThingProcessor:
      java.lang.IllegalStateException: OptionsHolder not initialized yet
```

Whether an order-sensitive pair works in the IDE is therefore luck. In the real
project this was found in it lands the wrong way round: Gradle puts
`protobuf-spi-impl` at position 3 and `mapstruct-processor` at 4, jdtls puts
`mapstruct-processor` at 2 and `protobuf-spi-impl` at 3, and every `@Mapper`
interface gets

```
Internal error in the mapping processor: java.lang.IllegalStateException:
ProcessingEnvOptionsHolder not initialized yet.
	at no.entur.mapstruct.spi.protobuf.ProcessingEnvOptionsHolder.containsKey
	at no.entur.mapstruct.spi.protobuf.ProtobufEnumMappingStrategy.initEnumPostfixOverrides
	... org.mapstruct.ap.MappingProcessor.process
	... org.eclipse.jdt.internal.apt.pluggable.core.dispatch.IdeAnnotationProcessorManager
```

with the consequence that no `*MapperImpl` is generated in the IDE at all, so
`Mappers.getMapper(...)` has nothing to find and every mapper is unresolved to
navigation and completion.

## Cause

Two places, both from `681c5f72` / [#2319](https://github.com/eclipse-jdtls/eclipse.jdt.ls/pull/2319)
"Support Gradle annotation processing" (2022-11-25).

`org.eclipse.jdt.ls.core/gradle/apt/init.gradle`, the model builder jdtls injects
into the Gradle build, collects into a `HashSet`:

```groovy
Set<File> processors = new HashSet<>()
List<String> compilerArgs = new LinkedList<>()     // order preserved here
collectApConfiguration(project, "compileJava", processors, compilerArgs)
```

`collectApConfiguration` does `processors.addAll(apPath.getFiles())`, and
`FileCollection.getFiles()` is already in path order — so the order is correct
on arrival and discarded on the next line. Note `compilerArgs` beside it does
use an ordered collection.

`GradleBuildSupport.updateAnnotationProcessorConfiguration` then walks that set
into the factory path:

```java
IFactoryPath factoryPath = AptConfig.getDefaultFactoryPath(javaProject);
for (File processor : processors) {
    factoryPath.addExternalJar(processor);
}
```

## Fix

`git diff` in this repo's sibling checkout of jdtls, on branch
`fix/apt-factorypath-order`:

1. `init.gradle`: `new HashSet<>()` → `new LinkedHashSet<>()`, so Gradle's order
   survives the trip through the Tooling API.
2. `GradleBuildSupport`: add the jars in reverse.

Step 2 is needed because `addExternalJar` adds to the **head** of the path, not
the tail. With step 1 alone the written file came out as exactly Gradle's order
reversed. That is not visible from `addExternalJar`'s name or signature, but it
is unambiguous in the bytecode: `addExternalJar` and `addEntryToHead` both
delegate to the same private `FactoryPath.internalAdd`, and `FactoryPath` stores
`_path` in the reverse of path order — `getAllContainers()` and
`getEnabledContainers()` both run it through a private `getReversed()` before
handing it to `FactoryPathUtil.encodeFactoryPath`. So iterating a path in order
and calling `addExternalJar` on each element reverses it, and feeding it
backwards is the correct use of the API.

`check_order.py` asserts the final file matches Gradle, so it will catch it if
that ever changes.

Verified with both steps applied — on the reproducer:

```
  orders identical: True
  gradle: holder first;  jdtls: holder first
  jdtls reports no error on Foo.java
```

and on the real project: `.factorypath` in Gradle's exact order, no error on any
`@Mapper` interface, and `CountryMapperImpl` / `DownstreamHeatPumpParametersMapperImpl`
generated by jdtls where previously nothing was.

## Not already reported

Searched `eclipse-jdtls/eclipse.jdt.ls` and `redhat-developer/vscode-java` for
factorypath / annotation-processor-order / mapstruct issues. The MapStruct ones
that exist are unrelated causes — vscode-java
[#3668](https://github.com/redhat-developer/vscode-java/issues/3668) (duplicate
generation in multi-module Maven),
[#3836](https://github.com/redhat-developer/vscode-java/issues/3836) and
[#3843](https://github.com/redhat-developer/vscode-java/issues/3843) (impl not
generated after a version bump),
[#4145](https://github.com/redhat-developer/vscode-java/issues/4145) (NPE), and
jdt.ls [#971](https://github.com/eclipse-jdtls/eclipse.jdt.ls/issues/971)
(lombok java agent). Nothing about path order.

## Workaround

None from the client side — the order is decided inside jdtls, and there is no
setting for it. `java.import.gradle.annotationProcessing.enabled: false` removes
the error by removing annotation processing, which also removes every other
generated source.

---

# Issue draft

*For https://github.com/eclipse-jdtls/eclipse.jdt.ls/issues/new — everything
below is the issue body.*

**Title:** Gradle's annotation processor path order is not preserved in `.factorypath`, so claims-nothing processors are never initialized

jdtls collects a project's annotation processors into a `HashSet` before writing
`.factorypath`, so ECJ discovers processors in rehashed order rather than the
order Gradle gives javac.

Discovery order is load-bearing. Both javac and ECJ stop discovering processors
once every annotation present has been claimed, so a processor that claims no
annotations — one that exists only to have `init()` called, to capture the
`ProcessingEnvironment` for a non-processor collaborator to read — is
initialized only if it precedes the processors that do the claiming. Reorder the
path and it silently never runs, and the collaborator reads an uninitialized
static.

The result is an IDE-only compile error on sources that `./gradlew` builds
cleanly.

### Cause

[`gradle/apt/init.gradle`](https://github.com/eclipse-jdtls/eclipse.jdt.ls/blob/master/org.eclipse.jdt.ls.core/gradle/apt/init.gradle#L61):

```groovy
Set<File> processors = new HashSet<>()
List<String> compilerArgs = new LinkedList<>()     // ordered
collectApConfiguration(project, "compileJava", processors, compilerArgs)
```

`collectApConfiguration` does `processors.addAll(apPath.getFiles())` and
`FileCollection.getFiles()` is already in path order, so the order is correct on
arrival and dropped on the next line. `GradleBuildSupport` then iterates that
set into `IFactoryPath.addExternalJar`.

Both were introduced by `681c5f72` / #2319.

### Steps to reproduce

A minimal build with a verify script is at
https://github.com/skagedal/reproducers/tree/main/jdtls-apt-processor-init-skipped —
two processor jars, one claiming an annotation and one claiming nothing but
reading the other's static, plus filler jars so a rehash is certain to reorder.

1. `python3 verify/check_order.py`.
2. Phase 1 shows plain javac compiling with the claims-nothing processor first
   and failing with it second, so the input really is order-sensitive.
3. Phase 2 shows the `.factorypath` jdtls writes in a different order from the
   one Gradle reports, and the resulting error on the annotated class.

Real-world instance: any Gradle project using MapStruct together with
`no.entur.mapstruct.spi:protobuf-spi-impl`, whose `ProcessingEnvOptionsHolder`
is exactly such a claims-nothing processor. Gradle orders it ahead of
`mapstruct-processor`; jdtls orders it behind, and every `@Mapper` interface
then reports

```
Internal error in the mapping processor: java.lang.IllegalStateException:
ProcessingEnvOptionsHolder not initialized yet.
```

with no `*MapperImpl` generated in the IDE.

### Suggested fix

`new HashSet<>()` → `new LinkedHashSet<>()` in `init.gradle` carries Gradle's
order through the Tooling API.

That alone is not sufficient, because `IFactoryPath.addExternalJar` adds to the
*head* of the path rather than the tail — it shares `FactoryPath.internalAdd`
with `addEntryToHead`, and `FactoryPath` stores `_path` in reverse of path order,
which `getAllContainers()`/`getEnabledContainers()` undo via a private
`getReversed()`. So the loop in `GradleBuildSupport` also has to feed the jars in
backwards:

```java
List<File> ordered = new ArrayList<>(processors);
Collections.reverse(ordered);
for (File processor : ordered) {
    factoryPath.addExternalJar(processor);
}
```

With both changes the `.factorypath` matches Gradle's order exactly, on the
reproducer and on the real project — where the error clears and the previously
missing `*MapperImpl` sources get generated.

Happy to open a PR if this looks right. One question if so: `addExternalJar`'s
head-insertion is load-bearing here but is not documented on `IFactoryPath`, and
every other caller in-tree adds a single jar, where it does not matter. Worth a
javadoc note?
