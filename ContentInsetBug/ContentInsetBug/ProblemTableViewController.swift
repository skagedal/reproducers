
import UIKit

private enum TableRow {
    case header
    case contentRow(String)
}

class ProblemTableViewController: UITableViewController {

    private let previewCell = HeaderCell()
    
    private var hidePreview = false
    
    private let tableRows: [TableRow] = [.header, .contentRow("First row"), .contentRow("Second row")]

    // MARK: - Life cycle
    
    init() {
        super.init(style: .plain)
    }
    
    required init?(coder aDecoder: NSCoder) { fatalError() }
    
    override func viewDidLoad() {
        super.viewDidLoad()
        
        tableView.register(UITableViewCell.self, forCellReuseIdentifier: "contentCell")
        updateContentInset()
    }
    
    func toggleHidePreview() {
        hidePreview = !hidePreview
        updateContentInset()
    }
    
    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        return tableRows.count
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        switch tableRows[indexPath.row] {
        case .header:
            return previewCell
        case let .contentRow(string):
            let cell = tableView.dequeueReusableCell(withIdentifier: "contentCell", for: indexPath)
            cell.textLabel?.text = string
            return cell
        }
    }

    override func tableView(_ tableView: UITableView, heightForRowAt indexPath: IndexPath) -> CGFloat {
        switch tableRows[indexPath.row] {
        case .header:
            return HeaderCell.height
        case .contentRow(_):
            return 64
        }
    }

    // Un-commenting out this solves the problem
    
//    override func tableView(_ tableView: UITableView, estimatedHeightForRowAt indexPath: IndexPath) -> CGFloat {
//        return self.tableView(tableView, heightForRowAt: indexPath)
//    }
    
    // MARK: - Other private
    
    private func updateContentInset() {
        let previewAdjustment = hidePreview ? -HeaderCell.height : 0
        if #available(iOS 11.0, *) {
            tableView.contentInset.top = previewAdjustment
        } else {
            tableView.contentInset.top = 64 + previewAdjustment
        }
    }
}

