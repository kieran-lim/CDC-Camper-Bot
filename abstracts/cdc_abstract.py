from typing import Any

# List of template attributes to be created for each field type
# Each attribute will be created with a suffix for each field type (e.g., days_in_view_practical, days_in_view_pt)
# The second element of each sublist is the type constructor (list, dict, str) to initialize the attribute
attribute_templates = [
    # Tracks dates visible in the current calendar view
    ["days_in_view", list],  
    # Maps date+time keys to web element IDs for interaction
    ["web_elements_in_view", dict],  
    # Tracks time slots visible in the current calendar view
    ["times_in_view", list],  

    # Stores currently available session slots
    ["available_sessions", dict],  

    # Stores sessions that the bot has reserved but not confirmed
    ["reserved_sessions", dict],  
    # Stores sessions already booked by the user
    ["booked_sessions", dict],  
    # The name of the lesson type (e.g., "Class 3A Motorcar")
    ["lesson_name", str],  

    # Sessions that are available and earlier than currently booked ones
    ["earlier_sessions", dict],  
    # Previous state of earlier_sessions for comparison
    ["cached_earlier_sessions", dict],  
]


# Enum-like class defining the different types of bookable sessions
class Types:
    PRACTICAL = "practical"  # Practical driving lessons
    PT = "pt"  # Practical driving test


# Dynamically creates a list of all field types defined in the Types class
# This enables automatic processing of all session types without hardcoding
field_types = [attr for attr in dir(Types) if not callable(getattr(Types, attr)) and not attr.startswith("__")]


class CDCAbstract:
    # Initializes the base class with user credentials and browser settings
    def __init__(self, username, password, headless=False):
        self.username = username
        self.password = password
        self.headless = headless

        # Dynamically create attributes for each field type
        # For example: days_in_view_practical, booked_sessions_pt, etc.
        for field_type in field_types:
            field_type_str = getattr(Types, field_type)
            for attribute_template in attribute_templates:
                # Creates and initializes the attribute with its appropriate type
                setattr(self, f"{attribute_template[0]}_{field_type_str}", attribute_template[1]())

        # Field-specific flags for tracking booking state
        # PRACTICAL session flags
        self.can_book_next_practical = True  # Whether user is eligible to book next practical lesson
        self.has_auto_reserved_practical = False  # Whether bot has auto-reserved a practical lesson

        # PT (Practical Test) session flags
        self.can_book_next_pt = True  # Whether user is eligible to book practical test

    # String representation of the object for debugging and logging
    def __str__(self):
        blacklist_attr_names = "captcha_solver,"  # Attributes to exclude from string representation
        abstract_str = "# ------------------------------------- - ------------------------------------ #\n"
        abstract_str += "CDC_ABSTRACT\n"

        # Mask sensitive information
        abstract_str += f"user = ######\n"  # {str(self.username)}\n"
        abstract_str += f"password = ######\n"  # {str(self.password)}\n"
        abstract_str += f"headless = {str(self.headless)}\n"

        abstract_str += "\n"

        # Get all non-callable attributes that don't start with '__'
        abstract_attr = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        
        # Group attributes by field type for better readability
        for field_type in field_types:
            abstract_str += f"# {str(field_type)}\n"

            field_type_str = getattr(Types, field_type)
            for attr in abstract_attr:
                # Only show attributes for this field type and not in blacklist
                if (field_type_str in attr) and (attr not in blacklist_attr_names):
                    abstract_str += f"# {str(attr)} = {str(getattr(self, attr))}\n"
            abstract_str += "\n"
        abstract_str += "# ------------------------------------- - ------------------------------------ #"

        return abstract_str

    # Resets all attributes for all field types
    # Used at the end of a checking cycle or when restarting
    def reset_attributes_for_all_fieldtypes(self):
        for field_type in field_types:
            self.reset_attributes_with_fieldtype(getattr(Types, field_type))

    # Resets all attributes for a specific field type
    # Used to clear state between checking cycles
    def reset_attributes_with_fieldtype(self, field_type: str):
        # Attributes to preserve during reset
        whitelisted_attributes = ["cached_earlier_sessions"]
        
        # Reset each attribute to its initial empty state
        for attribute_template in attribute_templates:
            attribute = attribute_template[0]
            if attribute not in whitelisted_attributes:
                self.set_attribute_with_fieldtype(attribute, field_type, attribute_template[1]())

        # Reset field-specific flags
        if field_type == Types.PRACTICAL:
            self.can_book_next_practical = True
            self.has_auto_reserved_practical = False

        if field_type == Types.PT:
            self.can_book_next_pt = True

    # General attribute getter
    # Rarely used directly - the fieldtype version is more common
    def get_attribute(self, attribute: str):
        return getattr(self, attribute)

    # General attribute setter
    # Rarely used directly - the fieldtype version is more common
    def set_attribute(self, attribute: str, value: Any):
        setattr(self, attribute, value)

    # Gets an attribute specific to a field type (e.g., available_sessions_practical)
    # This is the main way website_handler.py accesses data for a specific session type
    def get_attribute_with_fieldtype(self, attribute: str, field_type: str):
        return getattr(self, f"{attribute}_{field_type}")

    # Sets an attribute specific to a field type
    # This is the main way website_handler.py stores data for a specific session type
    def set_attribute_with_fieldtype(self, attribute: str, field_type: str, value: Any):
        setattr(self, f"{attribute}_{field_type}", value)
