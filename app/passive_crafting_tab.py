# app/passive_crafting_tab.py
import customtkinter as ctk


class PassiveCraftingTab(ctk.CTkFrame):
    def __init__(self, master, data_manager):
        super().__init__(master, fg_color="transparent")
        self.data_manager = data_manager

        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Passive Crafting Queue")
        self.scrollable_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.load_initial_data()
        self.data_manager.subscribe("crafting_update", self.update_table)

    def load_initial_data(self):
        crafting_data = self.data_manager.oneOffQuery("crafting_queue")
        self.update_table(crafting_data)

    def format_time(self, seconds):
        """Converts seconds to a M:SS format."""
        if seconds < 0:
            return "Done"
        mins, secs = divmod(seconds, 60)
        return f"{mins:02d}:{secs:02d}"

    def update_table(self, data):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        headers = ["Item Name", "Time Remaining"]
        for i, header in enumerate(headers):
            ctk.CTkLabel(self.scrollable_frame, text=header, font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=i, padx=10, pady=5
            )

        if not data:
            ctk.CTkLabel(self.scrollable_frame, text="Crafting queue is empty.").grid(row=1, column=0, columnspan=2, pady=10)
            return

        for row_idx, item in enumerate(data, start=1):
            ctk.CTkLabel(self.scrollable_frame, text=item["item"]).grid(row=row_idx, column=0, padx=10, pady=2, sticky="w")
            ctk.CTkLabel(self.scrollable_frame, text=self.format_time(item["time_left"])).grid(
                row=row_idx, column=1, padx=10, pady=2, sticky="e"
            )
