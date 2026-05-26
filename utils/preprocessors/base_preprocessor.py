class BasePreprocessor:
    """Shared data transforms used across all preprocessors.

    Subclasses call these methods in their own preprocess_* methods to build
    a pipeline suited to their data shape (elements, fixtures, history, etc.).
    """

    def __init__(self, data=None, teams_data=None):
        self.data = data
        self.teams_data = teams_data
        self.team_mapping = self._build_team_mapping()

    def _build_team_mapping(self):
        """Return a dict mapping team ID → short_name, or {} if teams_data is absent."""
        if self.teams_data is None:
            return {}
        return dict(zip(self.teams_data["id"], self.teams_data["short_name"], strict=False))

    def map_element_type_to_position(self):
        """Add a 'position' column by mapping element_type integers to GK/DEF/MID/FWD."""
        self.data["position"] = self.data["element_type"].map(
            {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
        )

    def replace_team_ids_with_names(self, column_names):
        """Replace integer team IDs in the given columns with their short names. Returns self.data."""
        if self.team_mapping:
            for column_name in column_names:
                self.data[column_name] = self.data[column_name].map(self.team_mapping)
        return self.data

    def create_full_name(self):
        """Add a 'full_name' column combining first_name and second_name."""
        self.data["full_name"] = self.data["first_name"] + " " + self.data["second_name"]
