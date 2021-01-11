from PIL import Image
import PIL
import itertools
import random
import re

#{
 # Expecting string in the form of:
 # e1011s0101
 
 # '0' => Zero (White - Red)
 # '1' => One (Gray - Blue)
 
 # 'a' => '0' after addition (FINAL)
 # 'b' => '1' after addition (FINAL)
 # 'c' => '0' Carry a '1', finalize to 'a' (Preserved) (FINAL)
 # 't' => '0' Temporary. Carry a 1, reset to '0'
 
 # 'w' => 'a' carrying '0' (SUMMING)
 # 'x' => 'a' carrying '1' (SUMMING)
 # 'y' => 'b' carrying '0' (SUMMING)
 # 'z' => 'b' carrying '1' (SUMMING)
 
 # 'B' => Blank symbol
 # 'e' => "equals"
 # 'f' => "finished". Triggers 'a' -> '0', 'b' -> '1'
 # 'g' => 'e' carrying '0' (no sum)
 # 'h' => 'e' carrying '1' (no sum)
 # 'i' => 'e' carrying '0' (SUMMING)
 # 'j' => 'e' carrying '1' (SUMMING)
 
 # 's' => "sum/separator". 
 # 'u' => 's' carrying '0' (SUMMING) (left)
 # 'v' => 's' carrying '1' (SUMMING) (left)
 
 #   On the left of the sum, just transfers digits to opposite side of 'e', replacing with 's':
 # '2' => Zero carrying zero (no sum)
 # '4' => Zero carrying one (no sum)
 # '3' => One  carrying zero (no sum)
 # '5' => One  carrying one (no sum)
 # 'd' => "delete". Always turns into 's'. Means we're moving this digit and need to buffer for one generation.
 
 #   On the right of the sum, moves pointer to the end, then begins transferring digits over to sum them
 # 'p' => '0' carrying pointer
 # 'q' => '1' carrying pointer
#}

regexes = {
    # Basic decompositions
    r".[024pt].": '0',  # Always return to '0' state.
    r".[135q].": '1',   # Always return to '1' state.
    r".[awxc].": 'a',   # Finalize 'a' ('0') as 'a'
    r".[byz].": 'b',    # Finalize 'b' ('1') as 'b'
    r".B.": 'B',        # By default don't change
    r".[eghij].": 'e',  # Always return e,g,h to e
    r".f.": 'B',        # Final Accepting State
    r".[dsuv].": 's',   # Always degrade to 's'.

    # Right side prioritization
    r"[sqp]0.": 'p',    # Set a '0' pointer
    r"[spq]1.": 'q',    # Set a '1' pointer
    r"[pq]BB": 's',     # Set 's' at the end to trick it into thinking it's normal.
    r".[ds][u23]": 'u',      # 's' starts carrying
    r".[ds][v45]": 'v',      # 's' starts carrying

    # Left side prioritization
    r".0s": '2',    # Start carrying '0' left
    r".1s": '5',    # start carrying '1' left
    r".0[23g]": '2',    # '0'-Continue carrying '0'
    r".0[45h]": '4',    # '0'-Continue carrying '1'
    r".1[23g]": '3',    # '1'-Continue carrying '0'
    r".1[45h]": '5',    # '1'-Continue carrying '1'

    # 'Equals' Shenanigans
    r".e[23]": 'g', # Carry '0' over
    r".e[45]": 'h', # Carry '1' over
    r".eu": 'i',    # Carry '0' (SUMMING) over
    r".ev": 'j',    # Carry '1' (SUMMING) over

    # Sums
    r".0[iwy]": 'a',    # '0' plus '0', finalize a/0
    r".0[jxzct]": 'b',  # '0' plus '1', finalize b/1
    r".1[iwy]": 'b',    # '1' plus '0', finalize a/0

    # Carries
    r".1[jxz]": 'c',    # '1' plus '1'. Preserves a '0' that's been carried. Finalize to 'a'
    r".1[ct]": 't',        # '1' plus '1'. Temporary. Carry the '1'. Resets to '0'
    r".B[ct]": 'y',     # ' Roll over a 1 into a new digit

    # Pass ints (SUMMING) over a sum
    r".a[iwy]": 'w',    # 'a' passes over a '0'
    r".a[jxz]": 'x',    # 'a' passes over a '1'
    r".b[iwy]": 'y',    # 'b' passes over a '0'
    r".b[jxz]": 'z',    # 'b' passes over a '1'

    r".B[23g]": '0',    # Fill in a blank with '0'
    r".B[45h]": '1',    # Fill in a black with '1'

    # Finalization
    r".[2345pq]s": 'd', # Ensures carried value passes, automatically clears (buffer zone to avoid collissions)
    r"[sed]{2}B": 'B',  # Clean up after everything is finished
    r".eB": 'f',        # Summation is finished, start finalization.
    r".[ac][01f]": '0', # Finalize as a '0'
    r".b[01f]": '1',    # Finalize as a '1'
}

unique_checks = []

class CellularAutomata():
    def __init__(self, input_string, automata_input_bits=3, number_of_colors=2,
                    random_first_row=False, img_width=100, img_height=300):
        self.automata_input_bits = automata_input_bits
        self.number_of_colors = number_of_colors
        self.random_first_row = random_first_row
        self.input_string = input_string

        # Proportion the image based on number of bits in `input_size`
        # e.g. for `input_size` 3, make the pic 2:1. For `input_size` 5, it's 4:1
        self.image_size = (img_width, img_height)
        self.ca_width, self.ca_height = img_width, img_height

        self.colors = {
            "B": (0, 0, 0), # Black

            # What's better than this? Just numbers carrying numbers
            "0": (255, 255, 255), # White
            "1": (128, 128, 128), # Gray
            "2": (255, 192, 0), # Sunflower
            "3": (255, 128, 0), # Orange
            "4": (0, 255, 255), # Cyan
            "5": (0, 128, 255), # Peri

            # Sum and relatives
            "s": (255, 0, 0), # Red
            "d": (128, 0, 0), # Maroon
            "u": (255, 180, 180), # Light Pink
            "v": (255, 64, 64),   # Bright Pink

            # Pointers
            "p": (192, 192, 255),   # Light... tan? 
            "q": (64, 64, 32),    # Dark tan. Fuck this.

            # The many states of Equals signs
            "e": (0, 255, 0), # Green
            "g": (192, 255, 0), # Lime 
            "h": (0, 192, 0), # Another green. idfk.
            "i": (255, 255, 0), # Yellow
            "j": (0, 192, 192), # Teal?
            "f": (0, 64, 0), # Forest Green?

            # Finalization, Baby!
            "a": (255, 100, 0), # Red-ish.
            "b": (0, 100, 255), # Blue-ish
            "c": (163, 64, 255), # Purple
            "t": (80, 0, 150), # The other purple.
            "w": (255, 128, 64), # The rest of them. god DAMN.kjla sdfjha
            "x": (150, 64, 0),
            "y": (64, 142, 255),
            "z": (0, 50, 128),
        }

    def _decide_value_by_rule(self, row, cell_index):
        value = "unassigned"

        # First cell being used as input
        p_cell = cell_index - self.automata_input_bits//2

        # Values of cell and its two neighbors
        rule_input = "".join([row[j % len(row)] for j in range(p_cell, p_cell + self.automata_input_bits)])

        if rule_input not in unique_checks:
            unique_checks.append(rule_input)

        # Iterate through each RegEx in `regexes` and apply them in order if they match
        for exp in regexes:
            if re.match(exp, rule_input):
                value = regexes[exp]
        if value == "unassigned":
            print("ABORTING NOW.")
            print("Unknown Rule input: " + rule_input)
            return "ABORT"

        return value


    def create_automata_image(self):
        # Create a row of '0's as a filler
        prev_row = ['B' for _ in range(self.ca_width + 1)]

        # If we have a randomly assigned first row, randomly decide values for each cell
        if self.random_first_row:
            prev_row = [random.choice([color for color in self.colors.keys()]) for _ in range(self.ca_width)]
        else:
            # Center the problem string on the first row
            prev_row[self.ca_width//2-len(self.input_string) : self.ca_width//2 + len(self.input_string) + 1] = list(self.input_string)

        im = Image.new("RGB", self.image_size, "#000000")
        cellular_automata_image = im.load()
        # Create image row by row
        for image_row in range(1, self.ca_height):
            new_row = prev_row
            #print(len(new_row))
            for cell_index, row_cell in enumerate(new_row):
                #print(row_cell)
                cell_color = self.colors[row_cell]
                try:
                    cellular_automata_image[cell_index+1, image_row+1] = cell_color
                except: pass
            new_row = [self._decide_value_by_rule(prev_row, cell_index) for cell_index in range(len(prev_row))]
            if new_row == prev_row:
                print("Cellular Automata Halted")
                break
            if "ABORT" in new_row:
                break
            prev_row = new_row
        im.save(f"TM_Binary_Sum_{self.input_string}{'_r'*self.random_first_row}.png")
        im.show()
        #print(unique_checks)


def main():
    new_automata = CellularAutomata("e0000s1000s1011", 3, 5, False)
    new_automata.create_automata_image()

if __name__ == '__main__':
    main()
