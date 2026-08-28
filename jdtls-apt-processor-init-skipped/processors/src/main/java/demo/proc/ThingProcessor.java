package demo.proc;

import java.util.Set;
import javax.annotation.processing.AbstractProcessor;
import javax.annotation.processing.RoundEnvironment;
import javax.annotation.processing.SupportedAnnotationTypes;
import javax.lang.model.SourceVersion;
import javax.lang.model.element.Element;
import javax.lang.model.element.TypeElement;
import javax.tools.Diagnostic;

/**
 * Claims the annotation the app uses, and needs OptionsHolder's static.
 * Stands in for org.mapstruct.ap.MappingProcessor reaching
 * ProtobufEnumMappingStrategy, which reads ProcessingEnvOptionsHolder.
 */
@SupportedAnnotationTypes("demo.app.Thing")
public class ThingProcessor extends AbstractProcessor {

    @Override
    public boolean process(Set<? extends TypeElement> annotations, RoundEnvironment round) {
        for (TypeElement annotation : annotations) {
            for (Element target : round.getElementsAnnotatedWith(annotation)) {
                try {
                    OptionsHolder.optionsOrThrow();
                } catch (IllegalStateException e) {
                    processingEnv.getMessager().printMessage(
                            Diagnostic.Kind.ERROR,
                            "Internal error in ThingProcessor: " + e, target);
                }
            }
        }
        return false;
    }

    @Override
    public SourceVersion getSupportedSourceVersion() {
        return SourceVersion.latestSupported();
    }
}
