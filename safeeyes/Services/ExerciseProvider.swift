import Foundation
import os

@MainActor
public final class ExerciseProvider: ObservableObject {
    public static let shared = ExerciseProvider()

    private var allExercises: [BreakContent] = []
    private var lastExerciseId: String?

    public init() {
        loadExercises()
    }

    private func loadExercises() {
        // Attempt to load Exercises.json from main bundle or module resources
        if let url = Bundle.main.url(forResource: "Exercises", withExtension: "json") ??
                     Bundle(for: ExerciseProvider.self).url(forResource: "Exercises", withExtension: "json") {
            do {
                let data = try Data(contentsOf: url)
                allExercises = try JSONDecoder().decode([BreakContent].self, from: data)
                Log.app.info("Loaded \(self.allExercises.count, privacy: .public) exercises from bundle")
                return
            } catch {
                Log.app.error("Failed to decode Exercises.json: \(error.localizedDescription, privacy: .public)")
            }
        }

        // Fallback default exercises in case bundled file cannot be loaded directly
        allExercises = [
            BreakContent(id: "20-20-20", title: "20-20-20 Rule", instruction: "Look at an object at least 20 feet away for 20 seconds.", symbol: "eye", kind: .short),
            BreakContent(id: "blink", title: "Blink Slowly", instruction: "Close your eyes gently, pause for 2 seconds, then open slowly.", symbol: "sparkles", kind: .short),
            BreakContent(id: "circles", title: "Eye Circles", instruction: "Roll your eyes slowly in a circle, then reverse direction.", symbol: "arrow.triangle.2.circlepath", kind: .short),
            BreakContent(id: "palming", title: "Palming", instruction: "Cup your warm hands gently over your closed eyes.", symbol: "hand.raised.fill", kind: .short),
            BreakContent(id: "stretch", title: "Neck & Shoulders", instruction: "Roll your shoulders back and gently tilt your neck.", symbol: "figure.mind.and.body", kind: .long),
            BreakContent(id: "walk", title: "Stand and Walk", instruction: "Stand up, stretch your legs, and look around.", symbol: "figure.walk", kind: .long)
        ]
    }

    public func nextExercise(for kind: BreakKind) -> BreakContent? {
        guard !allExercises.isEmpty else { return nil }

        let targetKindStr = kind.rawValue
        let matching = allExercises.filter { $0.kind.rawValue == targetKindStr || $0.kind == .both }
        let pool = matching.isEmpty ? allExercises : matching

        let candidates = pool.filter { $0.id != lastExerciseId }
        let chosen = (candidates.isEmpty ? pool : candidates).randomElement() ?? pool.first

        if let chosen = chosen {
            lastExerciseId = chosen.id
        }
        return chosen
    }
}
