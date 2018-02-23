
import UIKit

final class ProblemViewController: UIViewController {

    private let tableViewController = ProblemTableViewController()
    
    init() {
        super.init(nibName: nil, bundle: nil)

        navigationItem.leftBarButtonItem = UIBarButtonItem(title: "Toggle Preview",
                                                           style: .plain,
                                                           target: self,
                                                           action: #selector(togglePreviewTapped))
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Cause Problem",
                                                            style: .plain,
                                                            target: self,
                                                            action: #selector(causeProblemWasTapped))
    }
    
    required init?(coder aDecoder: NSCoder) { fatalError() }
    
    override func viewDidLoad() {
        super.viewDidLoad()

        addChildViewController(tableViewController)
        tableViewController.view.frame = view.bounds
        tableViewController.view.autoresizingMask = [.flexibleHeight, .flexibleWidth]
        view.addSubview(tableViewController.view)
        tableViewController.didMove(toParentViewController: self)
    }

    @objc func togglePreviewTapped(_ send: Any) {
        tableViewController.toggleHidePreview()
    }
    
    @objc func causeProblemWasTapped(_ sender: Any) {
        tableViewController.tableView.reloadData()
    }

}


