# GitHub Issue Templates Repository

This is a **template repository** containing standardized issue templates for bug reports and feature requests. Use this as a template when creating new repositories to automatically include these issue templates.

## 📋 What's Included

- **Bug Report Template** - Structured form for reporting bugs with severity levels
- **Feature Request Template** - Comprehensive form for suggesting new features
- **Config File** - Disables blank issues and provides helpful links

## 🚀 How to Use This Template

### For New Repositories

1. When creating a new repository on GitHub, select **"Repository template"** dropdown
2. Choose this repository as the template
3. All issue templates will be automatically included in your new repo

### For Existing Repositories

If you want to add these templates to an existing repository:

1. Copy the entire `.github` folder to your repository
2. Commit and push the changes
3. The templates will be available when creating new issues

## 📝 Templates Overview

### Bug Report
- Clear description fields
- Step-by-step reproduction steps
- Expected vs actual behavior
- Severity dropdown (Critical/High/Medium/Low)
- Environment information
- Screenshots and logs section

### Feature Request
- Problem statement
- Proposed solution
- Alternatives considered
- Priority levels
- Feature type checkboxes
- Use case description
- Mockups/examples section
- Contribution willingness checkbox

## ⚙️ Customization

You can customize these templates by editing the YAML files in `.github/ISSUE_TEMPLATE/`:

- `bug_report.yml` - Modify bug report fields and options
- `feature_request.yml` - Modify feature request fields and options
- `config.yml` - Update contact links with your repository URLs

### Update Contact Links

Don't forget to update the URLs in `config.yml` with your actual repository information:
```yaml
- name: Question or Discussion
  url: https://github.com/YOUR-USERNAME/YOUR-REPO/discussions
```

Replace `YOUR-USERNAME/YOUR-REPO` with your actual GitHub username and repository name.

## 🎯 Making This a Template Repository

To make this repository a template on GitHub:

1. Go to your repository settings
2. Scroll down to the "Template repository" section
3. Check the box ✅ "Template repository"
4. Save changes

Now you can use this repository as a template for all your future projects!

## 📖 Learn More

- [GitHub Issue Templates Documentation](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)
- [Creating Issue Forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)

---

**Note**: After using this template for a new repository, remember to update the `config.yml` file with your repository-specific URLs!
