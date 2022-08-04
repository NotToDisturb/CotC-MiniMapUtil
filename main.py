from PIL import Image, ImageDraw, ImageOps, ImageFont
import json
import os


def empty_warp():
    return {
        "id": -1,
        "from": [],
        "to": ""
    }


class MiniMap:
    debug = False

    actors_list = []
    actors_data = {}
    warp_data = {}

    path_width = 100
    margin = 400
    width = -1
    height = -1
    offset_x = -1
    offset_y = -1

    font = ImageFont.truetype("arial.ttf", 90)

    def __init__(self, path_actors_data):
        self.process_path_actors_data(path_actors_data)
        self.compute_bounds()
        self.image, self.draw = self.get_image_and_drawer()

    def get_image(self):
        return ImageOps.flip(self.image)

    def process_path_actors_data(self, path_actors_data):
        for actor_name, actor_data in path_actors_data.items():
            if actor_name.startswith("PathActor"):
                self.add_actor(actor_name, actor_data)
                self.actors_list.append(actor_name)
                if actor_data["FastTravel"] != "None":
                    self.extract_warps_from_data(actor_name, actor_data)
                if actor_data["UniqueLabel"] != "None":
                    self.extract_warp_to_data(actor_name, actor_data)
                    
    def compute_bounds(self):
        top = max(self.actors_data.values(), key=lambda vertex: vertex["y"])["y"]
        bottom = min(self.actors_data.values(), key=lambda vertex: vertex["y"])["y"]
        left = min(self.actors_data.values(), key=lambda vertex: vertex["x"])["x"]
        right = max(self.actors_data.values(), key=lambda vertex: vertex["x"])["x"]

        self.width = right - left + self.margin
        self.height = top - bottom + self.margin
        self.offset_x = abs(left) + self.margin / 2
        self.offset_y = abs(bottom) + self.margin / 2

    def get_image_and_drawer(self):
        image = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        return image, draw
    
    def add_actor(self, name, data):
        self.actors_data[name] = {
            "name": name,
            "x": int(data["Y"]),
            "y": int(data["X"]),
            "hidden": data["HiddenPath"],
            "connections": [connection for connection in data["Link"] if connection != "None"],
            "warps_tp": data["FastTravel"],
            "warp_dest": data["UniqueLabel"]
        }

    def generate_warp_id(self):
        return len(self.warp_data.keys())

    def extract_warps_from_data(self, name, data):
        warp = self.warp_data.get(data["FastTravel"], None)
        if not warp:
            warp = empty_warp()
            warp["id"] = self.generate_warp_id()
        warp["from"].append(name)
        self.warp_data[data["FastTravel"]] = warp

    def extract_warp_to_data(self, name, data):
        warp = self.warp_data.get(data["UniqueLabel"], None)
        if not warp:
            warp = empty_warp()
            warp["id"] = self.generate_warp_id()
        warp["to"] = name
        self.warp_data[data["UniqueLabel"]] = warp

    def get_base_vertex(self, use_fallback=True):
        return self.actors_data["PathActorBP"] \
            if self.actors_data.get("PathActorBP", None) and not use_fallback\
            else self.actors_data[self.actors_list[0]]

    def get_sorted_connections(self, vertex):
        return sorted(vertex["connections"], key=lambda c: 0 if self.actors_data[c]["hidden"] else 1)

    def start_minimap(self):
        base_vertex = self.get_base_vertex(use_fallback=False)
        while len(self.actors_list) > 0:
            self.actors_list.remove(base_vertex["name"])
            for connection in self.get_sorted_connections(base_vertex):
                connection_vertex = self.actors_data[connection]
                self.actors_list.remove(connection_vertex["name"])
                next_hidden = base_vertex["hidden"] or connection_vertex["hidden"]
                self.connect_vertexes(base_vertex, connection_vertex, next_hidden)
                self.process_vertex(connection_vertex, next_hidden)
            self.process_vertex(base_vertex, base_vertex["hidden"])
            if len(self.actors_list) > 0:
                base_vertex = self.get_base_vertex()

    def connect_vertexes(self, current_vertex, next_vertex, hidden):
        hidden = hidden or next_vertex["hidden"]
        color = "gray" if hidden else "white"
        current_coords = (current_vertex["x"] + self.offset_x, current_vertex["y"] + self.offset_y)
        next_coords = (next_vertex["x"] + self.offset_x, next_vertex["y"] + self.offset_y)

        for connection in self.get_sorted_connections(next_vertex):
            connection_vertex = self.actors_data.get(connection, None)
            same_vertex = connection_vertex["name"] != current_vertex["name"]
            if connection_vertex and same_vertex:
                self.actors_list.remove(connection_vertex["name"])
                next_hidden = hidden or connection_vertex["hidden"]
                self.connect_vertexes(next_vertex, connection_vertex, next_hidden)
        self.draw.line((current_coords, next_coords), fill=color, width=100)
        self.process_vertex(next_vertex, hidden)

    def process_vertex(self, vertex, hidden):
        effective_x = vertex["x"] + self.offset_x
        effective_y = vertex["y"] + self.offset_y

        beautifier_color = "gray" if hidden else "white"
        self.draw_circle(effective_x, effective_y, self.path_width / 2, color=beautifier_color)

        self.process_warps_to(vertex, effective_x, effective_y)
        self.process_warp_dest(vertex, effective_x, effective_y)

        if self.debug:
            hidden_color = "red" if vertex["hidden"] else "green"
            self.draw_circle(effective_x, effective_y, self.path_width / 2, color=hidden_color)

    def process_warps_to(self, vertex, effective_x, effective_y):
        if vertex["warps_tp"] != "None":
            warp = self.warp_data[vertex["warps_tp"]]
            if warp["to"] != "":
                self.draw_circle(effective_x, effective_y, self.path_width * 2 / 3, color="darkcyan")
            else:
                self.draw_circle(effective_x, effective_y, self.path_width * 2 / 3, color="darkgreen")
            self.draw_text(effective_x, effective_y, str(warp["id"]), "white")

    def process_warp_dest(self, vertex, effective_x, effective_y, show_extra=False):
        if vertex["warp_dest"] != "None":
            warp = self.warp_data[vertex["warp_dest"]]
            if len(warp["from"]) != 0:
                self.draw_circle(effective_x, effective_y, self.path_width * 2 / 3, color="darkcyan")
                self.draw_text(effective_x, effective_y, str(warp["id"]), "white")
            elif show_extra:
                self.draw_circle(effective_x, effective_y, self.path_width * 2 / 3, color="darkslategray")
                self.draw_text(effective_x, effective_y, str(warp["id"]), "white")

    def draw_circle(self, x, y, radius, color):
        coords_a = (x - radius, y - radius)
        coords_b = (x + radius, y + radius)
        self.draw.ellipse((coords_a, coords_b), fill=color)

    def draw_square(self, x, y, to_side, color):
        top_left = (x - to_side, y - to_side)
        bottom_right = (x + to_side, y + to_side)
        self.draw.rectangle((top_left, bottom_right), fill=color)

    def draw_text(self, x, y, text, color):
        text_size = self.draw.textbbox((0, 0), text, font=self.font)
        text_image = Image.new("RGBA", (text_size[2], text_size[3]), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_image)

        text_draw.text((0, 0), text, fill=color, font=self.font)
        text_image = ImageOps.flip(text_image)

        center_x = int(x - text_size[2] / 2)
        center_y = int(y - text_size[3] / 2)
        self.image.paste(text_image, (center_x, center_y), text_image)

    def draw_cross(self, x, y, color, to_side, width):
        top_left = (x - to_side, y - to_side)
        bottom_left = (x - to_side, y + to_side)
        top_right = (x + to_side, y - to_side)
        bottom_right = (x + to_side, y + to_side)

        self.draw.line((top_left, bottom_right), fill=color, width=width)
        self.draw.line((top_right, bottom_left), fill=color, width=width)


def export_result(result, folder, text_file):
    os.makedirs(folder, exist_ok=True)
    result.save(os.path.join(folder, text_file + ".png"))


def main():
    print("===========================================\n"
          "       MiniMapUtil - CotC datamining\n"
          "            built by Disturbo\n"
          "===========================================\n")
    minimap_path = input("Enter the path to the PathActors file: ")
    output_folder = input("Enter the path to the desired output folder: ")

    with open(minimap_path) as file:
        data = json.load(file)[0]
        minimap = MiniMap(data)
        minimap.start_minimap()

        file_name = os.path.splitext(os.path.basename(minimap_path))[0]
        export_result(minimap.get_image(), output_folder, file_name)


if __name__ == "__main__":
    main()
