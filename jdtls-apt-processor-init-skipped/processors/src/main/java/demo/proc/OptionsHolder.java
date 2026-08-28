package demo.proc;

import java.util.Map;
import javax.annotation.processing.AbstractProcessor;
import javax.annotation.processing.ProcessingEnvironment;
import javax.annotation.processing.RoundEnvironment;
import javax.annotation.processing.SupportedAnnotationTypes;
import javax.annotation.processing.SupportedOptions;
import javax.lang.model.SourceVersion;
import javax.lang.model.element.TypeElement;
import java.util.Set;

/**
 * A processor that exists only to capture the compiler's options into a static,
 * for a non-processor collaborator to read later. It claims no annotations.
 *
 * This is the exact shape of no.entur.mapstruct.spi.protobuf.ProcessingEnvOptionsHolder
 * (protobuf-spi-impl), whose static is read by ProtobufEnumMappingStrategy — a
 * MapStruct SPI, not a processor, so it has no ProcessingEnvironment of its own.
 */
@SupportedAnnotationTypes({}) // deliberately empty: it wants init(), not process()
@SupportedOptions("demo.opt")
public class OptionsHolder extends AbstractProcessor {

    private static Map<String, String> OPTIONS;

    @Override
    public synchronized void init(ProcessingEnvironment env) {
        super.init(env);
        OPTIONS = Map.copyOf(env.getOptions());
    }

    @Override
    public boolean process(Set<? extends TypeElement> annotations, RoundEnvironment round) {
        return false;
    }

    @Override
    public SourceVersion getSupportedSourceVersion() {
        return SourceVersion.latestSupported();
    }

    /** Mirrors ProcessingEnvOptionsHolder.containsKey / getOption. */
    public static Map<String, String> optionsOrThrow() {
        if (OPTIONS == null) {
            throw new IllegalStateException("OptionsHolder not initialized yet.");
        }
        return OPTIONS;
    }
}
