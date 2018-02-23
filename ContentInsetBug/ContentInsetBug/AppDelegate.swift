
import UIKit

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplicationLaunchOptionsKey: Any]?) -> Bool {

        let window = UIWindow()
        let nav = UINavigationController(rootViewController: ProblemViewController())
        window.rootViewController = nav
        window.makeKeyAndVisible()
        self.window = window

        return true
    }
}

