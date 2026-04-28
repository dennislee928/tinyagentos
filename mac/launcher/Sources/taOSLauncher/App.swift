import AppKit
import Foundation

@main
struct AppEntry {
    static func main() {
        let app = NSApplication.shared
        let delegate = TaOSAppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        app.run()
    }
}

final class TaOSAppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var menuBar: NSMenu!
    private var serverProcess: ServerProcess?
    private var windowController: WindowController!
    private var keyboardMonitor = KeyboardMonitor()
    private var sparkle = SparkleBridge()
    private let port: Int = 7117

    func applicationDidFinishLaunching(_ notification: Notification) {
        installStatusItem()
        startServer()
        windowController = WindowController(serverPort: port)
        keyboardMonitor.install()
        sparkle.startAutomaticUpdates()

        NSWorkspace.shared.notificationCenter.addObserver(
            self, selector: #selector(windowWillClose(_:)),
            name: NSWindow.willCloseNotification, object: nil
        )
    }

    func applicationWillTerminate(_ notification: Notification) {
        let server = serverProcess
        let group = DispatchGroup()
        group.enter()
        Task {
            await server?.stop(gracefulTimeoutSeconds: 5)
            group.leave()
        }
        _ = group.wait(timeout: .now() + 7)
    }

    private func installStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "taOS"
        let actions = MenuBar.Actions(
            openDesktop: { [weak self] in self?.openDesktop() },
            openMobile:  { [weak self] in self?.openMobile() },
            togglePause: { },
            openPreferences: { },
            checkForUpdates: { [weak self] in self?.sparkle.checkForUpdates() },
            quit: { NSApp.terminate(nil) }
        )
        menuBar = MenuBar.buildMenu(actions: actions, isPaused: false)
        statusItem.menu = menuBar
    }

    private func startServer() {
        let resources = Bundle.main.resourceURL!
        let python = resources.appendingPathComponent("python/bin/python3")
        let taosRoot = resources.appendingPathComponent("taos")
        let containerBin = resources.appendingPathComponent("bin/container")

        let dataDir = FileManager.default
            .homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/taOS")
        let logDir = FileManager.default
            .homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/taOS")

        let env: [String: String] = [
            "PYTHONPATH": taosRoot.path,
            "TAOS_DATA_DIR": dataDir.path,
            "TAOS_HOST": "127.0.0.1",
            "TAOS_PORT": "\(port)",
            "TAOS_CONTAINER_BIN": containerBin.path,
        ]

        let server = ServerProcess(
            executable: python,
            arguments: ["-m", "tinyagentos"],
            env: env,
            logFile: logDir.appendingPathComponent("server.log")
        )
        do {
            try server.start()
            self.serverProcess = server
        } catch {
            NSLog("[taOS] server failed to start: \(error)")
            statusItem.button?.title = "taOS ⚠"
            return
        }

        Task {
            let url = URL(string: "http://127.0.0.1:\(port)/api/health")!
            let ready = await server.waitForReady(timeoutSeconds: 15, healthURL: url)
            if !ready {
                await MainActor.run { self.statusItem.button?.title = "taOS ⚠" }
            }
        }
    }

    private func openDesktop() {
        if windowController.mode != .fullscreen { windowController.toggleMode() }
        NSApp.setActivationPolicy(.regular)
        windowController.showWindow()
        keyboardMonitor.fullscreen = true
    }

    private func openMobile() {
        if windowController.mode != .phone { windowController.toggleMode() }
        NSApp.setActivationPolicy(.regular)
        windowController.showWindow()
        keyboardMonitor.fullscreen = false
    }

    @objc private func windowWillClose(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        keyboardMonitor.fullscreen = false
    }
}
