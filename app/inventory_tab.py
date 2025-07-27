# app/inventory_tab.py
import customtkinter as ctk


class InventoryTab(ctk.CTkFrame):
    def __init__(self, master, data_manager):
        super().__init__(master, fg_color="transparent")
        self.data_manager = data_manager

        # Using a scrollable frame to hold the table content
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Claim Inventory")
        self.scrollable_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Initial data load
        self.load_initial_data()

        # Subscribe to future updates
        self.data_manager.subscribe("inventory_update", self.update_table)

    def load_initial_data(self):
        inventory_data = self.data_manager.oneOffQuery("inventory")
        self.update_table(inventory_data)

    def update_table(self, data):
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Create table headers
        headers = ["Item Name", "Quantity"]
        for i, header in enumerate(headers):
            ctk.CTkLabel(self.scrollable_frame, text=header, font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=i, padx=10, pady=5
            )

        # Populate table with new data
        for row_idx, item in enumerate(data, start=1):
            ctk.CTkLabel(self.scrollable_frame, text=item["item"]).grid(row=row_idx, column=0, padx=10, pady=2, sticky="w")
            ctk.CTkLabel(self.scrollable_frame, text=str(item["quantity"])).grid(
                row=row_idx, column=1, padx=10, pady=2, sticky="e"
            )
