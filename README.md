# Real Estate Information Extractor - `rea-info-bot`

Real Estate Information Extractor, or `rea-info-bot`, is a Python-based tool designed to scrape and extract real estate data for analysis and insights.

## Description

This tool provides an automated way to gather information on real estate listings. It's particularly useful for data analysts, researchers, and professionals in the real estate industry who are looking to aggregate data without manually visiting each listing.

## Getting Started

### Dependencies

- Python 3.6+
- Libraries: See `requirements.txt` for a full list of dependencies.

### Setting Up Your Development Environment

To set up your development environment, follow these steps:

# Clone the repository
git clone https://github.com/yourusername/rea-info-bot.git

# Navigate to the project directory
cd rea-info-bot

# Set up a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows use `venv\Scripts\activate`
source venv/bin/activate

# Install the dependencies
pip install -r requirements.txt

# Setup Poe token
I've used an existing project for using Poe in python - thanks to [poe-wrapper]([https://github.com/yourusername/rea-info-bot/contributors](https://pypi.org/project/poe-api-wrapper/))
Follow their guide for getting a Poe token. Then replace it into the code:
```
PoeApi("YOUR_TOKEN")
```

**Note:** The `venv/` directory is not to be committed to your version control system.

### Running the Application

With the virtual environment activated and the dependencies installed, you can run the scraper using the following command:

```bash
python your_project_code/poe_scraper.py -area <location>
```

It features a terminal argument 'area' - used for passing the location of which you want to scrape.

```bash
example: python your_project_code/poe_scraper.py -area utrecht
```

## Contributing

Contributions to `rea-info-bot` are welcome! Please read through our contribution guidelines to learn about our development process, how to propose bugfixes and improvements, and how to build and test your changes to the project.

## Authors

- **Your Name** - *Initial work* - [YourGitHubProfile](https://github.com/yourusername)

See also the list of [contributors](https://github.com/yourusername/rea-info-bot/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Hat tip to anyone whose code was used as inspiration.
- Special thanks to contributors and mentors.
- Anyone else you want to give credit to.

```

Make sure to replace `yourusername` with your actual GitHub username and `Your Name` with your name or your organization's name. Additionally, update the `Acknowledgments` section and any other placeholder text with real data as needed. If you have a `LICENSE` file, also include a link to that file in the `License` section.
