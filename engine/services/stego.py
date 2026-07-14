from PIL import Image
import io

def encode_text_in_image(image_path: str, secret_text: str, output_path: str) -> bool:
    """
    Encodes secret text inside the pixels of an image using LSB steganography.
    Saves the output as a PNG to preserve pixel values losslessly.
    """
    try:
        # Load image and convert to RGBA
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size
        
        # Append delimiter so we know where text ends during extraction
        delimiter = "##END##"
        data = secret_text + delimiter
        
        # Convert text to binary string
        binary_data = ''.join(format(ord(char), '08b') for char in data)
        data_len = len(binary_data)
        
        if data_len > width * height * 3:
            raise ValueError("Secret text is too long for this image size.")
            
        pixels = img.load()
        data_index = 0
        
        for y in range(height):
            for x in range(width):
                if data_index >= data_len:
                    break
                    
                r, g, b, a = pixels[x, y]
                
                # Encode bit into Red channel
                if data_index < data_len:
                    r = (r & ~1) | int(binary_data[data_index])
                    data_index += 1
                    
                # Encode bit into Green channel
                if data_index < data_len:
                    g = (g & ~1) | int(binary_data[data_index])
                    data_index += 1
                    
                # Encode bit into Blue channel
                if data_index < data_len:
                    b = (b & ~1) | int(binary_data[data_index])
                    data_index += 1
                    
                pixels[x, y] = (r, g, b, a)
                
            if data_index >= data_len:
                break
                
        # Save image as PNG (lossless to prevent compression from wiping bits)
        img.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"Steganography encoding failed: {e}")
        return False

def decode_text_from_image(image_path: str) -> str:
    """
    Extracts the hidden text from an LSB encoded image.
    """
    try:
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size
        pixels = img.load()
        
        binary_bits = []
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                binary_bits.append(str(r & 1))
                binary_bits.append(str(g & 1))
                binary_bits.append(str(b & 1))
                
        # Convert bits to characters
        all_bytes = [binary_bits[i:i+8] for i in range(0, len(binary_bits), 8)]
        decoded_chars = []
        
        for b_arr in all_bytes:
            if len(b_arr) < 8:
                break
            char_bin = "".join(b_arr)
            char_code = int(char_bin, 2)
            decoded_chars.append(chr(char_code))
            
        decoded_text = "".join(decoded_chars)
        
        # Check for delimiter
        if "##END##" in decoded_text:
            return decoded_text.split("##END##")[0]
            
        return ""
    except Exception as e:
        print(f"Steganography decoding failed: {e}")
        return ""
