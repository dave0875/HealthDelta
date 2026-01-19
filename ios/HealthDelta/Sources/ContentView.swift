import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 12) {
            Text("HealthDelta")
                .font(.title)
            Text("CI bootstrap build")
                .font(.subheadline)
        }
        .padding()
    }
}

#Preview {
    ContentView()
}

