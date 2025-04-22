package tech.skagedal;

import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;

import java.util.List;
import java.util.Objects;
import java.util.stream.Stream;

public class Main {
    @NonNull
    public List<@Nullable String> getStrings() {
        // Sonar says: "This method's return value is marked "@NonNull" but null is returned."
        return Stream.of("one", "two", "three")
            .map(Main::toUppercase)
            .filter(Objects::nonNull)
            .toList();
    }

    @Nullable
    private static String toUppercase(final String string) {
        if (string.equals("two")) {
            return null;
        }
        return string.toUpperCase();
    }

}