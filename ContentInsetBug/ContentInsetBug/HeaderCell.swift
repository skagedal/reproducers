
import UIKit

class HeaderCell: UITableViewCell {
    static let height: CGFloat = 190
    override init(style: UITableViewCellStyle, reuseIdentifier: String?) {
        super.init(style: style, reuseIdentifier: reuseIdentifier)

        let label = UILabel()
        label.text = """
            This is a cell that presents some header content.  It should be hidden when we search.
            To simulate this, tap Toggle Preview.  This sets a negative top contentInset.
            Then tap Cause Problem.  This just reloads the table view.
            """
        label.font = UIFont.preferredFont(forTextStyle: .footnote)
        label.numberOfLines = 0
        label.textAlignment = .left
        label.translatesAutoresizingMaskIntoConstraints = false
        contentView.addSubview(label)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 16),
            label.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: 16),
            label.centerYAnchor.constraint(equalTo: contentView.centerYAnchor)
            ])
    }
    
    required init?(coder aDecoder: NSCoder) { fatalError() }
}

