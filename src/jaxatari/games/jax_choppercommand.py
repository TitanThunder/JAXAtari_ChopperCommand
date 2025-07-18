"""

Lukas Bergholz, Linus Orlob, Vincent Jahn

"""
#TODO: replace fori_loops with vmap where possible

import os
from functools import partial
from typing import Tuple, NamedTuple, Callable
import jax
import jax.numpy as jnp
import chex
import pygame

import jaxatari.rendering.jax_rendering_utils as jru
import numpy as np
import jaxatari.spaces as spaces
from jaxatari.environment import JaxEnvironment, JAXAtariAction as Action, EnvState
from jaxatari.renderers import JAXGameRenderer
import time

class ChopperCommandConstants:
    # Game Constants
    WINDOW_WIDTH = 160 * 3
    WINDOW_HEIGHT = 210 * 3
    DEATH_PAUSE_FRAMES = 60

    WIDTH = 160
    HEIGHT = 192
    SCALING_FACTOR = 4

    # difficulty
    GAME_DIFFICULTY = 2

    # Chopper Constants TODO: Tweak these to match feeling of real game
    ACCEL = 0.03  # DEFAULT: 0.05 | how fast the chopper accelerates
    FRICTION = 0.02  # DEFAULT: 0.02 | how fast the chopper decelerates
    MAX_VELOCITY = 3.0  # DEFAULT: 3.0 | maximum speed
    DISTANCE_WHEN_FLYING = 10 # DEFAULT: 10 | How far the chopper moves towards the middle when flying for a longer amount of time
    LOCAL_PLAYER_OFFSET_SPEED = 1 # DEFAULT: 1 | How fast the chopper changes the on-screen position when changing its facing direction
    ALLOW_MOVE_OFFSET = 13 # DEFAULT: 13 | While in the no_move_pause, this is the offset measured from the left screen border where moving the chopper (exiting the pause) is allowed again
    PLAYER_ROTOR_SPEED = 3 # DEFAULT: 3 | The smaller this value, the faster the rotor blades of the player chopper spin

    # Score
    SCORE_PER_JET_KILL = 200
    SCORE_PER_CHOPPER_KILL = 100
    SCORE_PER_TRUCK_ALIVE = 100

    # Player Missile Constants
    PLAYER_MISSILE_WIDTH = 80 # Sprite size_x
    MISSILE_COOLDOWN_FRAMES = 8  # DEFAULT: 8 | How fast Chopper can shoot (higher is slower) TODO: Das müssen wir ändern und höher machen bei dem schweren Schwierigkeitsgrad
    MISSILE_SPEED = 10 # DEFAULT: 10 | Missile speed (higher is faster) TODO: tweak MISSILE_SPEED and MISSILE_COOLDOWN_FRAMES to match real game (already almost perfect)
    MISSILE_ANIMATION_SPEED = 6 # DEFAULT: 6 | Rate at which missile changes sprite textures (based on traveled distance of missile)

    # Enemy Missile Constants
    ENEMY_MISSILE_SPAWN_PROBABILITY = 0.01 # The probability that an enemy missiles spawns at one of the living enemies in each frame, if the missile of the giving enemy is not "alive". (Meaning that for 0.01 for example, an enemy shoots a missile on average 100 frames after its previous missile died).
    ENEMY_MISSILE_SPLIT_PROBABILITY = 0.05 # The probability that an enemy missiles splits in a frame
    ENEMY_MISSILE_MAXIMUM_Y_SPEED_BEFORE_SPLIT = 0.75 # Maximum speed (+ and -) of a missile before split. This means that for 2 for example, the missiles will have speeds between -2 and 2 (chosen randomly).
    ENEMY_MISSILE_Y_SPEED_AFTER_SPLIT = 2.5 # TODO: Make match real game

    # Colors
    BACKGROUND_COLOR = (0, 0, 139)  # Dark blue for sky
    PLAYER_COLOR = (187, 187, 53)  # Yellow for player helicopter
    ENEMY_COLOR = (170, 170, 170)  # Gray for enemy helicopters
    MISSILE_COLOR = (255, 255, 255)  # White for missiles
    SCORE_COLOR = (210, 210, 64)  # Score color

    # Object sizes and initial positions
    PLAYER_SIZE = (16, 9)  # Width, Height
    TRUCK_SIZE = (8, 7)
    JET_SIZE = (8, 6)
    CHOPPER_SIZE = (8, 9)
    PLAYER_MISSILE_SIZE = (80, 1) #Default (80, 1)
    ENEMY_MISSILE_SIZE = (2, 1)

    PLAYER_START_X = 0
    PLAYER_START_Y = 100

    X_BORDERS = (0, 160)
    PLAYER_BOUNDS = (0, 160), (52, 150)

    # Maximum number of objects
    MAX_TRUCKS = 12 # DEFAULT: 12 | How much trucks are spawned
    MAX_JETS = 12 # DEFAULT: 12 | the maximum amount of jets that can be spawned
    MAX_CHOPPERS = 12 # DEFAULT: 12 | the maximum amount of choppers that can be spawned
    MAX_ENEMIES = 12 # DEFAULT: 12 | the amount of enemies that are spawned
    MAX_PLAYER_MISSILES = 1 # DEFAULT: 1 | the original game allows only one missile per screen. The player_missile_step logic is adjusted automatically, if this is changed to more than 1.
    MAX_ENEMY_MISSILES = MAX_ENEMIES * 2 * 2 # Two missiles for every enemy (jets and choppers) (this does not mean, that there are always this many missiles on the screen/in the game)
    ENEMY_LANE_SWITCH_PROBABILITY = 0.05 # DEFAULT: 7 | how likely is it that en enemy switches a lane

    # Enemy movement
    JET_VELOCITY_LEFT = 1.5 # DEFAULT: 1.5 | How fast jets fly to the left
    JET_VELOCITY_RIGHT = 1 # DEFAULT: 1 | How fast jets fly to the right
    CHOPPER_VELOCITY_LEFT = 0.75 # DEFAULT: 0.75 | How fast choppers fly to the right
    CHOPPER_VELOCITY_RIGHT = 0.5 # DEFAULT: 0.5 | How fast choppers fly to the right
    ENEMY_OUT_OF_CYCLE_RIGHT = 64 # DEFAULT: 64 | How far enemies can fly around the truck fleet to the right
    ENEMY_OUT_OF_CYCLE_LEFT = 64 # DEFAULT: 64 | How far enemies cam fly around the truck fleet to the left
    ENEMY_MAXIMUM_SPAWN_OFFSET = 64 # DEFAULT: 64 | How far to the left and right of the middle truck enemies can spawn

    # Enemy Lanes

    ENEMY_LANE_OFFSET = 7 # DEFAULT: 7 | How much apart bottom and top lanes are from the middle lane

    ENEMY_LANE_7 = 66
    ENEMY_LANE_8 = ENEMY_LANE_7 - ENEMY_LANE_OFFSET
    ENEMY_LANE_6 = ENEMY_LANE_7 + ENEMY_LANE_OFFSET

    ENEMY_LANE_4 = 96
    ENEMY_LANE_5 = ENEMY_LANE_4 - ENEMY_LANE_OFFSET
    ENEMY_LANE_3 = ENEMY_LANE_4 + ENEMY_LANE_OFFSET

    ENEMY_LANE_1 = 126
    ENEMY_LANE_2 = ENEMY_LANE_1 - ENEMY_LANE_OFFSET
    ENEMY_LANE_0 = ENEMY_LANE_1 + ENEMY_LANE_OFFSET

    BOTTOM_LANES = jnp.array([ENEMY_LANE_0, ENEMY_LANE_1, ENEMY_LANE_2])
    MIDDLE_LANES = jnp.array([ENEMY_LANE_3, ENEMY_LANE_4, ENEMY_LANE_5])
    TOP_LANES = jnp.array([ENEMY_LANE_6, ENEMY_LANE_7, ENEMY_LANE_8])

    ALL_LANES = jnp.array([ENEMY_LANE_0, ENEMY_LANE_1, ENEMY_LANE_2, ENEMY_LANE_3, ENEMY_LANE_4, ENEMY_LANE_5, ENEMY_LANE_6, ENEMY_LANE_7, ENEMY_LANE_8])

    """
    Correct arrangement of lanes by height is:
    
    ENEMY_LANE_8
    ENEMY_LANE_7
    ENEMY_LANE_6
    
    ENEMY_LANE_5
    ENEMY_LANE_4
    ENEMY_LANE_3
    
    ENEMY_LANE_2
    ENEMY_LANE_1
    ENEMY_LANE_0
    
    """

    # Minimap
    MINIMAP_WIDTH = 48
    MINIMAP_HEIGHT = 16

    MINIMAP_POSITION_X = (WIDTH // 2) - (MINIMAP_WIDTH // 2) # TODO: Im echten Game wird die Minimap nicht mittig, sondern weiter links gerendert. Wir müssen besprechen ob wir das auch machen, dann müsste man nur diese Zahl hier ändern (finde es aber so schöner)
    MINIMAP_POSITION_Y = 165

    MINIMAP_RENDER_TRUCK_REFRESH_RATE = 8 # Higher is slower (Does not fully work yet)

    DOWNSCALING_FACTOR_WIDTH = WIDTH // MINIMAP_WIDTH
    DOWNSCALING_FACTOR_HEIGHT = HEIGHT // MINIMAP_HEIGHT

    #Object rendering
    TRUCK_SPAWN_DISTANCE = 248 # distance 240px + truck width

    FRAMES_DEATH_ANIMATION_ENEMY = 16
    FRAMES_DEATH_ANIMATION_TRUCK = 32 # TODO: Make match real game
    TRUCK_FLICKER_RATE = 3 # TODO: Make match real game

    PLAYER_FADE_OUT_START_THRESHOLD_0 = 0.25
    PLAYER_FADE_OUT_START_THRESHOLD_1 = 0.125

    # define object orientations
    FACE_LEFT = -1
    FACE_RIGHT = 1

    SPAWN_POSITIONS_Y = jnp.array([60, 90, 120])
    TRUCK_SPAWN_POSITIONS = 156

    # Debugging

    ENABLE_PLAYER_COLLISION = True
    ENABLE_ENEMY_MISSILE_TRUCK_COLLISION = True


class ChopperCommandState(NamedTuple):
    player_x: chex.Array                    # x-coordinate of the player’s chopper in world space
    player_y: chex.Array                    # y-coordinate of the player’s chopper in world space
    player_velocity_x: chex.Array           # horizontal velocity (momentum) of the player’s chopper; positive = moving right, negative = moving left
    local_player_offset: chex.Array         # offset of the player’s chopper from the screen center (used for scrolling logic and chopper’s on-screen position)
    player_facing_direction: chex.Array     # current facing direction of the player’s chopper: -1 = facing left, +1 = facing right, 0 = invalid
    score: chex.Array                       # current game score/points
    lives: chex.Array                       # number of remaining lives for the player
    save_lives: chex.Array                  # keeps track of how often the player was granted a life for reaching another 10000 score points
    truck_positions: chex.Array             # shape (MAX_TRUCKS, 4): for each truck, stores [x, y, direction (active flag), death_timer]
    jet_positions: chex.Array               # shape (MAX_JETS, 4): for each enemy jet, stores [x, y, direction (active flag), death_timer]
    chopper_positions: chex.Array           # shape (MAX_ENEMIES, 4): for each enemy chopper, stores [x, y, direction (active flag), death_timer]
    enemy_missile_positions: chex.Array     # shape (MAX_MISSILES, 4): for each enemy missile, stores [x, y, direction, did_split_flag]
    player_missile_positions: chex.Array    # shape (MAX_MISSILES, 4): for each player missile, stores [x, y, direction, x_coordinate of spawn point]
    player_missile_cooldown: chex.Array     # cooldown timer until the player can fire the next missile
    player_collision: chex.Array            # boolean flag indicating whether the player has collided this frame
    step_counter: chex.Array                # total number of game ticks/frames elapsed so far
    pause_timer: chex.Array                 # counter for how many frames remain in the game pause before respawning; 0 = fully dead, respawn initiated, 1 = either no lives left, infinite pause or ->, 1 - DEATH_PAUSE_FRAMES: counting down for the duration of pause, DEATH_PAUSE_FRAMES + 1 = death_pause, DEATH_PAUSE_FRAMES + 2 = no_move_pause
    obs_stack: chex.ArrayTree               # stacked sequence of past observations (for frame‐stacking in the agent)
    rng_key: chex.PRNGKey                   # current PRNG key for any stochastic operations (e.g., random enemy spawns)
    difficulty: chex.Array                  # states the difficulty which can be either 1 or 2
    enemy_speed: chex.Array                 # states the speed of the enemies e.g. all enemies are killed

class PlayerEntity(NamedTuple):
    x: jnp.ndarray
    y: jnp.ndarray
    o: jnp.ndarray
    width: jnp.ndarray
    height: jnp.ndarray
    active: jnp.ndarray

class EntityPosition(NamedTuple):
    x: jnp.ndarray
    y: jnp.ndarray
    width: jnp.ndarray
    height: jnp.ndarray
    active: jnp.ndarray

class ChopperCommandObservation(NamedTuple):
    player: PlayerEntity
    trucks: jnp.ndarray # Shape (MAX_TRUCKS, 5) - MAX_TRUCKS enemies, each with x,y,w,h,active
    jets: jnp.ndarray  # Shape (MAX_JETS, 5) - MAX_JETS enemies, each with x,y,w,h,active
    choppers: jnp.ndarray # Shape (MAX_CHOPPERS, 5) - MAX_CHOPPERS enemies, each with x,y,w,h,active
    enemy_missiles: jnp.ndarray  # Shape (MAX_MISSILES, 5)
    player_missile: EntityPosition
    player_score: jnp.ndarray
    lives: jnp.ndarray

class ChopperCommandInfo(NamedTuple):
    step_counter: jnp.ndarray  # Current step count
    all_rewards: jnp.ndarray  # All rewards for the current step

# RENDER CONSTANTS
def load_sprites():
    MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
    # Load sprites - no padding needed for background since it's already full size
    pl_chopper1 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/player_chopper/1.npy"))
    pl_chopper2 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/player_chopper/2.npy"))
    friendly_truck1 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/friendly_truck/1.npy"))
    friendly_truck2 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/friendly_truck/2.npy"))
    enemy_jet = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/enemy_jet/normal.npy"))
    enemy_chopper1 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/enemy_chopper/1.npy"))
    enemy_chopper2 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/enemy_chopper/2.npy"))
    enemy_bomb = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/bomb/1.npy"))

    bg_sprites = []
    for i in range(1, 161):
        temp = jru.loadFrame(os.path.join(MODULE_DIR, f"sprites/choppercommand/bg/{i}.npy"))
        bg_sprites.append(temp)
        bg_sprites[i - 1] = jnp.expand_dims(bg_sprites[i - 1], axis=0)

    pl_missile_sprites_temp = []
    for i in range(0, 16):
        temp = jru.loadFrame(os.path.join(MODULE_DIR, f"sprites/choppercommand/player_missiles/missile_{i}.npy"))
        pl_missile_sprites_temp.append(temp)
        pl_missile_sprites_temp[i] = jnp.expand_dims(pl_missile_sprites_temp[i], axis=0)

    minimap_mountains_temp = []
    for i in range(1, 9):
        temp = jru.loadFrame(os.path.join(MODULE_DIR, f"sprites/choppercommand/minimap/mountains/{i}.npy"))
        minimap_mountains_temp.append(temp)
        minimap_mountains_temp[i - 1] = jnp.expand_dims(minimap_mountains_temp[i - 1], axis=0)

    # Pad player helicopter sprites to match each other
    pl_chopper_sprites, _ = jru.pad_to_match([pl_chopper1, pl_chopper2])

    # Pad friendly truck sprites to match each other
    friendly_truck_sprites, _ = jru.pad_to_match([friendly_truck1, friendly_truck2])

    # Pad enemy jet sprites to match each other
    enemy_jet_sprites = [enemy_jet]

    # Pad enemy helicopter sprites to match each other
    enemy_heli_sprites, _ = jru.pad_to_match([enemy_chopper1, enemy_chopper2])

    # Pad player missile sprites to match each other
    pl_missile_sprites = pl_missile_sprites_temp

    # Pad enemy missile sprites to match each other
    enemy_missile_sprites = [enemy_bomb]

    # Background sprite (no padding needed)
    SPRITE_BG = jnp.concatenate(bg_sprites, axis=0) # jnp.expand_dims(bg1, axis=0)

    # Player helicopter sprites
    SPRITE_PL_CHOPPER = jnp.concatenate(
        [
            jnp.repeat(pl_chopper_sprites[0][None], 3, axis=0),    # PLAYER_ROTOR_SPEED = 3
            jnp.repeat(pl_chopper_sprites[1][None], 3, axis=0),    # PLAYER_ROTOR_SPEED = 3
        ]
    )

    # Friendly truck sprites
    SPRITE_FRIENDLY_TRUCK = jnp.concatenate(
        [
            jnp.repeat(friendly_truck_sprites[0][None], 4, axis=0),
            jnp.repeat(friendly_truck_sprites[1][None], 4, axis=0),
        ]
    )

    # Enemy jet sprite
    SPRITE_ENEMY_JET = jnp.repeat(enemy_jet_sprites[0][None], 1, axis=0)

    # Enemy helicopter sprites
    SPRITE_ENEMY_CHOPPER = jnp.concatenate(
        [
            jnp.repeat(enemy_heli_sprites[0][None], 4, axis=0),
            jnp.repeat(enemy_heli_sprites[1][None], 4, axis=0),
        ]
    )

    DIGITS = jru.load_and_pad_digits(os.path.join(MODULE_DIR, "./sprites/choppercommand/score/{}.npy"))
    LIFE_INDICATOR = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/score/chopper.npy"))

    #Death Sprites
    PLAYER_DEATH_1 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/player_chopper/death_1.npy"))
    PLAYER_DEATH_2 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/player_chopper/death_2.npy"))
    PLAYER_DEATH_3 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/player_chopper/death_3.npy"))

    ENEMY_DEATH_1 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/enemy_death/death_1.npy"))
    ENEMY_DEATH_2 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/enemy_death/death_2.npy"))
    ENEMY_DEATH_3 = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/enemy_death/death_3.npy"))

    # Player missile sprites
    SPRITE_PL_MISSILE = jnp.concatenate(pl_missile_sprites, axis=0)

    # Enemy missile sprites
    SPRITE_ENEMY_MISSILE = jnp.repeat(enemy_missile_sprites[0][None], 1, axis=0)

    #Everything having to do with the minimap
    MINIMAP_BG = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/minimap/background.npy"))
    MINIMAP_PLAYER = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/minimap/player.npy"))
    MINIMAP_TRUCK = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/minimap/truck.npy"))
    MINIMAP_ACTIVISION_LOGO = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/minimap/activision_logo.npy")) #delete if necessary
    MINIMAP_ENEMY = jru.loadFrame(os.path.join(MODULE_DIR, "sprites/choppercommand/minimap/enemy.npy"))
    MINIMAP_MOUNTAINS = jnp.concatenate(minimap_mountains_temp, axis=0)


    return (
        SPRITE_BG,
        SPRITE_PL_CHOPPER,
        SPRITE_FRIENDLY_TRUCK,
        SPRITE_ENEMY_JET,
        SPRITE_ENEMY_CHOPPER,
        SPRITE_PL_MISSILE,
        SPRITE_ENEMY_MISSILE,
        DIGITS,
        LIFE_INDICATOR,
        PLAYER_DEATH_1,
        PLAYER_DEATH_2,
        PLAYER_DEATH_3,
        ENEMY_DEATH_1,
        ENEMY_DEATH_2,
        ENEMY_DEATH_3,
        MINIMAP_BG,
        MINIMAP_MOUNTAINS,
        MINIMAP_PLAYER,
        MINIMAP_TRUCK,
        MINIMAP_ENEMY,
        MINIMAP_ACTIVISION_LOGO, #delete if necessary
    )

# Load sprites once at module level
(
    SPRITE_BG,
    SPRITE_PL_CHOPPER,
    SPRITE_FRIENDLY_TRUCK,
    SPRITE_ENEMY_JET,
    SPRITE_ENEMY_HELI,
    SPRITE_PL_MISSILE,
    SPRITE_ENEMY_MISSILE,
    DIGITS,
    LIFE_INDICATOR,
    PLAYER_DEATH_1,
    PLAYER_DEATH_2,
    PLAYER_DEATH_3,
    ENEMY_CHOPPER_DEATH_1,
    ENEMY_CHOPPER_DEATH_2,
    ENEMY_CHOPPER_DEATH_3,
    MINIMAP_BG,
    MINIMAP_MOUNTAINS,
    MINIMAP_PLAYER,
    MINIMAP_TRUCK,
    MINIMAP_ENEMY,
    MINIMAP_ACTIVISION_LOGO, #delete if necessary
) = load_sprites()

class JaxChopperCommand(JaxEnvironment[ChopperCommandState, ChopperCommandObservation, ChopperCommandInfo, ChopperCommandConstants]):
    def __init__(self, consts: ChopperCommandConstants = None, frameskip: int = 1, reward_funcs: list[Callable] =None):
        consts = consts or ChopperCommandConstants()
        super().__init__(consts)
        self.frameskip = frameskip
        if reward_funcs is not None:
            reward_funcs = tuple(reward_funcs)
        self.reward_funcs = reward_funcs
        self.action_set = [
            Action.NOOP,
            Action.FIRE,
            Action.UP,
            Action.RIGHT,
            Action.LEFT,
            Action.DOWN,
            Action.UPRIGHT,
            Action.UPLEFT,
            Action.DOWNRIGHT,
            Action.DOWNLEFT,
            Action.UPFIRE,
            Action.RIGHTFIRE,
            Action.LEFTFIRE,
            Action.DOWNFIRE,
            Action.UPRIGHTFIRE,
            Action.UPLEFTFIRE,
            Action.DOWNRIGHTFIRE,
            Action.DOWNLEFTFIRE
        ]
        self.frame_stack_size = 4
        self.obs_size = 5 + self.consts.MAX_JETS * 5 + self.consts.MAX_CHOPPERS * 5 + self.consts.MAX_PLAYER_MISSILES * 5 + 5 + 5
        self.renderer = ChopperCommandRenderer()

    def render(self, state: ChopperCommandState) -> jnp.ndarray:
        """Render the game state to a raster image."""
        return self.renderer.render(state)

    def flatten_entity_position(self, entity: EntityPosition) -> jnp.ndarray:
        return jnp.concatenate([entity.x, entity.y, entity.width, entity.height, entity.active])

    def flatten_player_entity(self, entity: PlayerEntity) -> jnp.ndarray:
        return jnp.concatenate([jnp.array([entity.x]), jnp.array([entity.y]), jnp.array([entity.o]), jnp.array([entity.width]), jnp.array([entity.height]), jnp.array([entity.active])])

    @partial(jax.jit, static_argnums=(0,))
    def obs_to_flat_array(self, obs: ChopperCommandObservation) -> jnp.ndarray:
        return jnp.concatenate([
            self.flatten_player_entity(obs.player),
            obs.trucks.flatten(),
            obs.jets.flatten(),
            obs.choppers.flatten(),
            obs.enemy_missiles.flatten(),
            self.flatten_entity_position(obs.player_missile),
            obs.player_score.flatten(),
            obs.lives.flatten(),
        ])

    def action_space(self) -> spaces.Discrete:
        return spaces.Discrete(len(self.action_set))

    # def get_action_space(self) -> jnp.ndarray: # deprecated
    #     return jnp.array(self.action_set)

    def observation_space(self) -> spaces.Dict:
        """Returns the observation space for Seaquest.
        The observation contains:
        - player: PlayerEntity (x, y, o, width, height, active)
        - sharks: array of shape (12, 5) with x,y,width,height,active for each shark
        - submarines: array of shape (12, 5) with x,y,width,height,active for each submarine
        - divers: array of shape (4, 5) with x,y,width,height,active for each diver
        - enemy_missiles: array of shape (4, 5) with x,y,width,height,active for each missile
        - surface_submarine: EntityPosition (x, y, width, height, active)
        - player_missile: EntityPosition (x, y, width, height, active)
        - collected_divers: int (0-6)
        - player_score: int (0-999999)
        - lives: int (0-3)
        - oxygen_level: int (0-255)
        """
        return spaces.Dict({
            "player": spaces.Dict({
                "x": spaces.Box(low=0, high=160, shape=(), dtype=jnp.int32),
                "y": spaces.Box(low=0, high=210, shape=(), dtype=jnp.int32),
                "o": spaces.Box(low=0, high=1, shape=(), dtype=jnp.int32),
                "width": spaces.Box(low=0, high=160, shape=(), dtype=jnp.int32),
                "height": spaces.Box(low=0, high=210, shape=(), dtype=jnp.int32),
                "active": spaces.Box(low=0, high=1, shape=(), dtype=jnp.int32),
            }),
            "trucks": spaces.Box(low=0, high=160, shape=(self.consts.MAX_TRUCKS, 4), dtype=jnp.int32),
            "jets": spaces.Box(low=0, high=160, shape=(self.consts.MAX_JETS, 4), dtype=jnp.int32),
            "choppers": spaces.Box(low=0, high=160, shape=(self.consts.MAX_CHOPPERS, 4), dtype=jnp.int32),
            "enemy_missiles": spaces.Box(low=0, high=160, shape=(self.consts.MAX_ENEMY_MISSILES, 4), dtype=jnp.int32),
            "player_missile": spaces.Dict({
                "x": spaces.Box(low=0, high=160, shape=(), dtype=jnp.int32),
                "y": spaces.Box(low=0, high=210, shape=(), dtype=jnp.int32),
                "width": spaces.Box(low=0, high=160, shape=(), dtype=jnp.int32),
                "height": spaces.Box(low=0, high=210, shape=(), dtype=jnp.int32),
                "active": spaces.Box(low=0, high=1, shape=(), dtype=jnp.int32),
            }),
            "collected_divers": spaces.Box(low=0, high=6, shape=(), dtype=jnp.int32),
            "player_score": spaces.Box(low=0, high=999999, shape=(), dtype=jnp.int32),
            "lives": spaces.Box(low=0, high=3, shape=(), dtype=jnp.int32),
        })

    def image_space(self) -> spaces.Box:
        """Returns the image space for ChopperCommand.
        The image is a RGB image with shape (160, 210, 3).
        """
        return spaces.Box(
            low=0,
            high=255,
            shape=(160, 210, 3),
            dtype=jnp.uint8,
        )

    @partial(jax.jit, static_argnums=(0, ))
    def _get_observation(self, state: ChopperCommandState) -> ChopperCommandObservation:
        # Create player (already scalar, no need for vectorization)
        player = PlayerEntity(
            x=state.player_x,
            y=state.player_y,
            o=state.player_velocity_x,
            width=jnp.array(self.consts.PLAYER_SIZE[0]),
            height=jnp.array(self.consts.PLAYER_SIZE[1]),
            active=jnp.array(1),  # Player is always active
        )

        # Define a function to convert enemy positions to entity format
        def convert_to_entity(pos, size):
            return jnp.array([
                pos[0],  # x position
                pos[1],  # y position
                size[0],  # width
                size[1],  # height
                pos[2] != 0,  # active flag
            ])

        # Apply conversion to each type of entity using vmap

        # Friendly trucks
        trucks = jax.vmap(lambda pos: convert_to_entity(pos, self.consts.TRUCK_SIZE))(
            state.truck_positions
        )

        # Enemy jets
        jets = jax.vmap(lambda pos: convert_to_entity(pos, self.consts.JET_SIZE))(
            state.jet_positions
        )

        # Enemy choppers
        choppers = jax.vmap(lambda pos: convert_to_entity(pos, self.consts.CHOPPER_SIZE))(
            state.chopper_positions
        )

        # Enemy missiles
        enemy_missiles = jax.vmap(lambda pos: convert_to_entity(pos, self.consts.ENEMY_MISSILE_SIZE))(
            state.enemy_missile_positions
        )

        # Player missile (scalar)
        missile_pos = state.player_missile_positions
        player_missile = EntityPosition(
            x=missile_pos[0],
            y=missile_pos[1],
            width=jnp.array(self.consts.PLAYER_MISSILE_SIZE[0]),
            height=jnp.array(self.consts.PLAYER_MISSILE_SIZE[1]),
            active=jnp.array(missile_pos[2] != 0),
        )

        # Return observation
        return ChopperCommandObservation(
            player=player,
            trucks=trucks,
            jets=jets,
            choppers=choppers,
            enemy_missiles=enemy_missiles,
            player_missile=player_missile,
            player_score=state.score,
            lives=state.lives,
        )

    @partial(jax.jit, static_argnums=(0,))
    def _get_info(self, state: ChopperCommandState, all_rewards: jnp.ndarray) -> ChopperCommandInfo:
        return ChopperCommandInfo(
            step_counter=state.step_counter,
            all_rewards=all_rewards,
        )

    @partial(jax.jit, static_argnums=(0,))
    def _get_env_reward(self, previous_state: ChopperCommandState, state: ChopperCommandState):
        return state.score - previous_state.score

    @partial(jax.jit, static_argnums=(0,))
    def _get_all_rewards(self, previous_state: ChopperCommandState, state: ChopperCommandState) -> jnp.ndarray:
        if self.reward_funcs is None:
            return jnp.zeros(1)
        rewards = jnp.array([reward_func(previous_state, state) for reward_func in self.reward_funcs])
        return rewards

    @partial(jax.jit, static_argnums=(0,))
    def _get_done(self, state: ChopperCommandState) -> bool:
        return state.lives < 0

    @partial(jax.jit, static_argnums=(0,))
    def check_collision_single(
            self, pos1, size1, pos2, size2
    ):
        """Check collision between two single entities"""
        # Calculate edges for rectangle 1
        rect1_left = pos1[0]
        rect1_right = pos1[0] + size1[0]
        rect1_top = pos1[1]
        rect1_bottom = pos1[1] + size1[1]

        # Calculate edges for rectangle 2
        rect2_left = pos2[0]
        rect2_right = pos2[0] + size2[0]
        rect2_top = pos2[1]
        rect2_bottom = pos2[1] + size2[1]

        # Check overlap
        horizontal_overlap = jnp.logical_and(
            rect1_left < rect2_right,
            rect1_right > rect2_left
        )

        vertical_overlap = jnp.logical_and(
            rect1_top < rect2_bottom,
            rect1_bottom > rect2_top
        )

        return jnp.logical_and(horizontal_overlap, vertical_overlap)

    @partial(jax.jit, static_argnums=(0,))
    def check_collision_batch(
            self, pos1, size1, pos2_array, size2
    ):
        """Check collision between one entity and an array of entities"""
        # Calculate edges for rectangle 1
        rect1_left = pos1[0]
        rect1_right = pos1[0] + size1[0]
        rect1_top = pos1[1]
        rect1_bottom = pos1[1] + size1[1]

        # Calculate edges for all rectangles in pos2_array
        rect2_left = pos2_array[:, 0]
        rect2_right = pos2_array[:, 0] + size2[0]
        rect2_top = pos2_array[:, 1]
        rect2_bottom = pos2_array[:, 1] + size2[1]

        # Check overlap for all entities
        horizontal_overlaps = jnp.logical_and(
            rect1_left < rect2_right,
            rect1_right > rect2_left
        )

        vertical_overlaps = jnp.logical_and(
            rect1_top < rect2_bottom,
            rect1_bottom > rect2_top
        )

        # Combine checks for each entity
        collisions = jnp.logical_and(horizontal_overlaps, vertical_overlaps)

        # Return true if any collision detected
        return jnp.any(collisions)

    def kill_entity(
            self,
            enemy_pos: chex.Array,
            death_timer: int
            ) -> chex.Array:
        return jnp.array([
            enemy_pos[0],  # x
            enemy_pos[1],  # y
            enemy_pos[2],  # direction
            death_timer  # death_timer
        ], dtype=enemy_pos.dtype)

    @partial(jax.jit, static_argnums=(0,))
    def check_missile_collisions( # TODO: improve
        self,
        missile_positions: chex.Array,  # (MAX_MISSILES, 4)
        enemy_positions: chex.Array,    # (N_ENEMIES, 2)
        on_screen_position: chex.Array,
        player_x: chex.Array,
        enemy_size: chex.Array,
    ) -> tuple[chex.Array, chex.Array, chex.Array]:
        """Check for collisions between player missiles and enemies, mit dynamischer Breitenanpassung."""

        def check_single_missile(missile):
            missile_x, missile_y, direction, _ = missile
            missile_active = missile[3] != 0

            def check_single_enemy(enemy_pos):
                enemy_active = enemy_pos[3] > self.consts.FRAMES_DEATH_ANIMATION_ENEMY

                # Sichtfeldgrenzen
                left_bound = player_x - on_screen_position
                right_bound = left_bound + self.consts.WIDTH

                new_missile = direction

                missile_left = missile_x
                missile_right = missile_x + self.consts.PLAYER_MISSILE_SIZE[0]

                # Dynamische Breite berechnen
                clipped_left = jnp.maximum(missile_left, left_bound)
                clipped_right = jnp.minimum(missile_right, right_bound)

                # Neue Breite
                clipped_width = jnp.maximum(0, clipped_right - clipped_left)

                # Missile ist zu klein → keine Kollision möglich
                too_small = clipped_width <= 0

                # Neue Position für Kollisionstest
                adjusted_pos = jnp.array([clipped_left, missile_y])
                adjusted_size = jnp.array([clipped_width, self.consts.PLAYER_MISSILE_SIZE[1]])

                collision = jnp.logical_and(
                    jnp.logical_and(
                        jnp.logical_and(
                            missile_active,
                            enemy_active
                        ),
                        jnp.logical_not(too_small)
                    ),
                    self.check_collision_single(adjusted_pos, adjusted_size, enemy_pos, enemy_size)
                )

                # Kill initialisieren (nicht endgültig tot)
                new_enemy_pos = jnp.where(collision,
                                          self.kill_entity(enemy_pos, self.consts.FRAMES_DEATH_ANIMATION_ENEMY),
                                          enemy_pos)

                # Missile deaktivieren bei Treffer
                new_missile = jnp.where(
                    collision,
                    jnp.array([0, 0, 0, 0], dtype=missile.dtype),
                    missile
                )

                # Punkte vergeben
                is_jet = enemy_size[1] == 6
                score_add = jnp.where(
                    jnp.logical_and(collision, enemy_pos[3] > self.consts.FRAMES_DEATH_ANIMATION_ENEMY),
                    jnp.where(
                        is_jet,
                        self.consts.SCORE_PER_JET_KILL,
                        self.consts.SCORE_PER_CHOPPER_KILL
                    ),
                    0
                )

                return new_enemy_pos, new_missile, score_add

            new_enemy_positions, new_missiles, score_add = jax.vmap(check_single_enemy)(enemy_positions)
            return new_enemy_positions, new_missiles[0], jnp.sum(score_add)                                 # in case of weird behavior: change the array addressing here

        new_enemy_positions, new_missiles, score_add = jax.vmap(check_single_missile)(missile_positions)
        return new_enemy_positions[0], new_missiles, jnp.sum(score_add)



    @partial(jax.jit, static_argnums=(0,))
    def check_player_collision_entity(
        self,
        player_x: chex.Array,
        player_y: chex.Array,
        player_velocity: chex.Array,
        entity_list: chex.Array,
        entity_size: Tuple[int, int],
        death_threshold: chex.Array,
        ) -> Tuple[chex.Array, chex.Array]:

        player_pos = jnp.array([player_x, player_y])
        offset = (self.consts.PLAYER_SIZE[0] // 2 - entity_size[0] // 2) - (player_velocity * self.consts.DISTANCE_WHEN_FLYING)

        def check_single(entity):
            #any_collision_inner, updated_entities = carry

            world_x, world_y = entity[0], entity[1]
            death_timer = entity[3]
            is_active = death_timer > death_threshold

            # Passe die Position an, wie sie auch im Renderer korrigiert wird
            adjusted_entity_pos = jnp.array([world_x + offset, world_y])

            # Prüfe Kollision nur bei aktiven Gegnern
            collision = jnp.logical_and(
                is_active,
                self.check_collision_single(player_pos, self.consts.PLAYER_SIZE, adjusted_entity_pos, entity_size)
            )

            # Markiere getroffenen Gegner
            new_entity = jnp.where(collision, self.kill_entity(entity, death_threshold), entity)

            return new_entity

        updated_entity_list = jax.vmap(check_single)(entity_list)

        return jnp.invert(jnp.array_equal(entity_list, updated_entity_list)), updated_entity_list

    @partial(jax.jit, static_argnums=(0,))
    def check_missile_truck_collisions(
            self,
            truck_positions: chex.Array,  # (MAX_TRUCKS, 4): [x, y, direction, death_timer]
            missile_positions: chex.Array,  # (MAX_MISSILES, 4): [x, y, direction, did_split_flag]
            truck_size: Tuple[int, int],  # (width, height)
            missile_size: Tuple[int, int],  # (width, height)
    ) -> Tuple[chex.Array, chex.Array]:

        def check_single_missile(missile, trucks):
            mx, my, _, _ = missile
            missile_active = my > 2

            def check_single_truck(truck):
                tx, ty, tdir, tdeath = truck
                truck_active = jnp.logical_and(tdir != 0, tdeath > 0)

                collision = (
                        missile_active & truck_active &
                        self.check_collision_single(
                            jnp.array([mx, my]), missile_size,
                            jnp.array([tx, ty]), truck_size
                        )
                )

                updated_truck = jnp.where(
                    collision,
                    jnp.array([tx, ty, tdir, self.consts.FRAMES_DEATH_ANIMATION_TRUCK], dtype=truck.dtype),
                    truck
                )

                return collision, updated_truck

            # Check all trucks against this missile
            collision_flags, updated_trucks = jax.vmap(check_single_truck)(trucks)

            # If any collision occurred, mark missile as dead
            collided = jnp.any(collision_flags)
            updated_missile = jnp.where(
                collided,
                jnp.array([0.0, 0.0, 0.0, 187.0], dtype=missile.dtype),
                missile
            )

            return updated_missile, updated_trucks, collision_flags

        # Apply to all missiles
        updated_results = jax.vmap(
            lambda m: check_single_missile(m, truck_positions)
        )(missile_positions)

        updated_missiles = updated_results[0]  # shape: (MAX_MISSILES, 4)
        updated_truck_list = updated_results[1]  # shape: (MAX_MISSILES, MAX_TRUCKS, 4)
        collision_flags_all = updated_results[2]  # shape: (MAX_MISSILES, MAX_TRUCKS)

        # Combine all truck updates from each missile pass
        def reduce_trucks(i, carry):
            combined = carry
            flags = collision_flags_all[i]
            trucks = updated_truck_list[i]
            return jnp.where(flags[:, None], trucks, combined)

        initial_trucks = truck_positions
        updated_trucks = jax.lax.fori_loop(0, missile_positions.shape[0], reduce_trucks, initial_trucks)

        return updated_trucks, updated_missiles

    """now can spawn enemies into fleets with different directions"""
    @partial(jax.jit, static_argnums=(0,))      #TODO: fix
    def initialize_enemy_positions(self, init_rng: chex.PRNGKey) -> tuple[chex.Array, chex.Array]:
        jet_positions = jnp.zeros((self.consts.MAX_ENEMIES, 4))
        chopper_positions = jnp.zeros((self.consts.MAX_ENEMIES, 4))

        fleet_start_x = -780
        fleet_spacing_x = 312
        fleet_count = 4
        units_per_fleet = 3
        vertical_spacing = 30
        y_start = self.consts.HEIGHT // 2 - (units_per_fleet // 2) * vertical_spacing
        key0, key1, key2 = jax.random.split(init_rng, 3)
        keys_for_direction = jax.random.split(key0, fleet_count)
        keys_for_chopper_amount = jax.random.split(key1, fleet_count)
        keys_for_offsets = jax.random.split(key2, fleet_count * units_per_fleet)

        carry = (jet_positions, chopper_positions, 0)

        def spawn_fleet(fleet_idx, carry):
            jet_positions, chopper_positions, global_idx = carry

            anchor_x = fleet_start_x + fleet_idx * fleet_spacing_x
            out_of_bounds = jnp.abs(self.consts.PLAYER_START_X - anchor_x) > 624
            anchor_x = jnp.where(out_of_bounds, anchor_x + 2*624, anchor_x)

            # Für jede Einheit eine zufällige Richtung
            directions = jax.random.choice(keys_for_direction[fleet_idx], jnp.array([-1, 1]), shape=(units_per_fleet,), replace=True)

            # Zufällige Anzahl Chopper
            chopper_count = jax.random.randint(keys_for_chopper_amount[fleet_idx], (), 0, units_per_fleet + 1)

            # X-Offsets
            x_offset_array = jnp.array(
                [jax.random.randint(keys_for_offsets[fleet_idx * units_per_fleet + 0], (), -self.consts.ENEMY_MAXIMUM_SPAWN_OFFSET + 5, self.consts.ENEMY_MAXIMUM_SPAWN_OFFSET - 5),
                jax.random.randint(keys_for_offsets[fleet_idx * units_per_fleet + 1], (), -self.consts.ENEMY_MAXIMUM_SPAWN_OFFSET + 5, self.consts.ENEMY_MAXIMUM_SPAWN_OFFSET - 5),
                jax.random.randint(keys_for_offsets[fleet_idx * units_per_fleet + 2], (), -self.consts.ENEMY_MAXIMUM_SPAWN_OFFSET + 5, self.consts.ENEMY_MAXIMUM_SPAWN_OFFSET - 5)])

            def place_unit(i, unit_carry):
                jet_positions, chopper_positions, jet_idx, chopper_idx = unit_carry
                y = y_start + i * vertical_spacing
                offset_x = x_offset_array[i]
                direction = directions[i]
                pos = jnp.array([anchor_x + offset_x, y, direction, self.consts.FRAMES_DEATH_ANIMATION_ENEMY + 5])

                is_chopper = i < chopper_count
                chopper_positions = jax.lax.cond(
                    is_chopper,
                    lambda cp: cp.at[chopper_idx].set(pos),
                    lambda cp: cp,
                    chopper_positions
                )
                jet_positions = jax.lax.cond(
                    is_chopper,
                    lambda jp: jp,
                    lambda jp: jp.at[jet_idx].set(pos),
                    jet_positions
                )

                jet_idx += jnp.where(is_chopper, 0, 1)
                chopper_idx += jnp.where(is_chopper, 1, 0)
                return jet_positions, chopper_positions, jet_idx, chopper_idx

            jet_positions, chopper_positions, jet_idx, chopper_idx = jax.lax.fori_loop(
                0, units_per_fleet, place_unit, (jet_positions, chopper_positions, global_idx, global_idx)
            )

            new_global_idx = global_idx + units_per_fleet
            return (jet_positions, chopper_positions, new_global_idx)

        jet_positions, chopper_positions, _ = jax.lax.fori_loop(
            0, fleet_count, spawn_fleet, carry
        )

        return jet_positions, chopper_positions

    @partial(jax.jit, static_argnums=(0,))
    def emit_enemy_speed(self, speed: chex.Array) -> chex.Array:
        return True

    @partial(jax.jit, static_argnums=(0,))
    def step_enemy_movement(
            self,
            truck_positions: chex.Array,
            jet_positions: chex.Array,
            chopper_positions: chex.Array,
            rng: chex.PRNGKey,
            state_player_x: chex.Array,
            local_player_offset: chex.Array,
            difficulty: chex.Array,
            enemy_speed: chex.Array,
    ) -> Tuple[chex.Array, chex.Array, chex.PRNGKey]:

        rng0, direction_rng = jax.random.split(rng)
        rng1, process_jet_rng = jax.random.split(rng0)
        return_rng, process_chopper_rng = jax.random.split(rng1)

        def emit_velocity() -> chex.Array:
            difficulty_value = jnp.where(difficulty == 1, 1, 1.5)
            jet_speed_right = (self.consts.JET_VELOCITY_RIGHT + enemy_speed) * difficulty_value
            jet_speed_left = (self.consts.JET_VELOCITY_LEFT + enemy_speed) * difficulty_value
            chopper_speed_right = (self.consts.CHOPPER_VELOCITY_RIGHT + enemy_speed) * difficulty_value
            chopper_speed_left = (self.consts.CHOPPER_VELOCITY_LEFT + enemy_speed) * difficulty_value

            return jnp.array([jet_speed_right, jet_speed_left, chopper_speed_right, chopper_speed_left])


        def move_enemy_x(pos: chex.Array, is_jet, move_x_is_in_range) -> chex.Array:
            is_active = pos[2] != 0

            def is_out_of_cycle(enemy_pos: chex.Array) -> chex.Array:
                # Auswahl der X-Positionen der mittleren trucks
                middle_trucks = jnp.array(
                    [
                        truck_positions[1][0],
                        truck_positions[4][0],
                        truck_positions[7][0],
                        truck_positions[10][0],
                    ]
                )

                # Berechne den absoluten Abstand zur enemy_position[0]
                distances = jnp.abs(middle_trucks - enemy_pos[0])

                # Finde den Index des kleinsten Abstands
                min_index = jnp.argmin(distances)

                nearest_middle_truck = middle_trucks[min_index]

                return jnp.logical_or(enemy_pos[0] > nearest_middle_truck + self.consts.ENEMY_OUT_OF_CYCLE_RIGHT,
                                      enemy_pos[0] < nearest_middle_truck - self.consts.ENEMY_OUT_OF_CYCLE_LEFT)


            def is_in_range_function():
                def check_if_out_of_cycle_jet_function():
                    def jet_is_out_of_cycle_function():

                        return jax.lax.cond( # jet_is_out_of_cycle_function
                            pos[2] == -1,
                            lambda _: jnp.array([pos[0] + pos[2] * -1 * emit_velocity()[1] - 1, pos[1], pos[2] * -1, pos[3]], dtype=jnp.float32), # if enemy direction is -1 and position out of bounds turn around by multiply direction with -1 (LEFT -> RIGHT) and adding the LEFT_VELOCITY * direction to the position
                            lambda _: jnp.array([pos[0] + pos[2] * -1 * emit_velocity()[0] - 1, pos[1], pos[2] * -1, pos[3]], dtype=jnp.float32), # if enemy direction is not -1 and position out of bounds turn around by multiply direction with -1 (RIGHT -> LEFT) and adding the RIGHT_VELOCITY * direction to the position
                            operand=None
                        )

                    def jet_is_not_out_of_cycle_function():

                        return jax.lax.cond( # jet_is_not_out_of_cycle_function
                            pos[2] == -1,
                            lambda _: jnp.array([pos[0] + pos[2] * emit_velocity()[1], pos[1], pos[2], pos[3]], dtype=jnp.float32), # if enemy direction is -1 and position is not out of bounds just add the LEFT_VELOCITY * direction onto the position
                            lambda _: jnp.array([pos[0] + pos[2] * emit_velocity()[0], pos[1], pos[2], pos[3]], dtype=jnp.float32), # if enemy direction is not -1 and position is not out of bounds just add the RIGHT_VELOCITY * direction onto the position
                            operand=None
                        )


                    return jax.lax.cond( # is_in_range_function
                        is_out_of_cycle(pos),                               # checks if enemy is out of cycle
                        lambda _: jet_is_out_of_cycle_function(),           # Jet is indeed out of bounds
                        lambda _: jet_is_not_out_of_cycle_function(),       # Jet is inside of bounds
                        operand=None
                    )


                def check_if_out_of_cycle_chopper_function():

                    def chopper_is_out_of_cycle_function():

                        return jax.lax.cond( # chopper_is_out_of_cycle_function
                            pos[2] == -1,
                            lambda _: jnp.array([pos[0] + pos[2] * -1 * emit_velocity()[3] - 1, pos[1], pos[2] * -1, pos[3]], dtype=jnp.float32),  # Since chopper is out of bounds, change its direction from left to right and do one step to the right + 1 to escape cycle (bounds) boundry
                            lambda _: jnp.array([pos[0] + pos[2] * -1 * emit_velocity()[2] - 1, pos[1], pos[2] * -1, pos[3]], dtype=jnp.float32), # Since chopper is out of bounds, change its direction from right to left and do one step to the left + 1 to escape cycle (bounds) boundry
                            operand=None
                        )

                    def chopper_is_not_out_of_cycle_function():

                        return jax.lax.cond( # chopper_is_not_out_of_cycle_function
                            pos[2] == -1,
                            lambda _: jnp.array([pos[0] + pos[2] * emit_velocity()[3], pos[1], pos[2], pos[3]], dtype=jnp.float32),  # Since chopper is inside of bounds, move chopper to the left by the defined speed
                            lambda _: jnp.array([pos[0] + pos[2] * emit_velocity()[2], pos[1], pos[2], pos[3]], dtype=jnp.float32), # Since chopper is inside of bounds, move chopper to the right by the defined speed
                            operand=None
                        )


                    return jax.lax.cond( # check_if_out_of_cycle_chopper_function
                        is_out_of_cycle(pos),
                        lambda _: chopper_is_out_of_cycle_function(),     # Chopper is indeed out of bounds
                        lambda _: chopper_is_not_out_of_cycle_function(), # Chopper is inside of bounds
                        operand=None
                    )


                return jax.lax.cond( # is_in_range_function
                    is_jet,
                    lambda _: check_if_out_of_cycle_jet_function(),       # Check if jet is out of bounds
                    lambda _: check_if_out_of_cycle_chopper_function(),   # Check if chopper is out of bounds
                    operand=None
                )


            def not_active_or_not_in_range(): # looks for in_range and active enemies from all fleets
                return jax.lax.cond(
                    move_x_is_in_range,
                    lambda _: pos,                                                      # is dead -> does not move at all
                    lambda _: jnp.array([pos[0] - 0.5, pos[1], pos[2], pos[3]]),        # moves the same speed as trucks to the left (fleet + trucks stay freezed)
                    operand=None
                )

            new_pos = jax.lax.cond(
                jnp.logical_and(is_active, move_x_is_in_range),
                lambda _: is_in_range_function(),           # Enemy is alive and is in the nearest fleet to the player
                lambda _: not_active_or_not_in_range(),     # Enemy is either dead or not part of the nearest fleet to the player.
                operand=None
            )


            out_of_bounds = jnp.abs(state_player_x - pos[0]) > 624
            wrapped_x = pos[0] + jnp.clip(state_player_x - pos[0], -1, 1) * 1248  # + pos[2] * 0.5
            wrapped_pos = jnp.array([wrapped_x, pos[1], pos[2], pos[3]])

            return jnp.where(out_of_bounds, wrapped_pos, new_pos)

        def move_enemy_y(pos: chex.Array, move_y_rng_key: chex.Array, middle_lane_rng_key: chex.Array, move_y_is_in_range: chex.Array):
            is_active = pos[2] != 0
            is_on_correct_lane = jnp.logical_or(pos[1] == (pos[3] - self.consts.FRAMES_DEATH_ANIMATION_ENEMY), pos[3] == self.consts.FRAMES_DEATH_ANIMATION_ENEMY + 5) # If enemy is on the lane defined in its lane flag, except if lane flag equals the reset state

            def dont_touch_position():
                return pos[1], pos[3]

            def move_or_dont():
                def dont_move_and_reset_lane_flag():
                    return pos[1], self.consts.FRAMES_DEATH_ANIMATION_ENEMY + 5.0

                def move():
                    def get_go_up():
                        return pos[1] - 0.5, pos[3]
                    def get_go_down():
                        return pos[1] + 0.5, pos[3]

                    lane_is_below = pos[1] < (pos[3] - self.consts.FRAMES_DEATH_ANIMATION_ENEMY)
                    return jax.lax.cond(lane_is_below,
                                        lambda _: get_go_down(),  # If lane is below, do one step towards ground
                                        lambda _: get_go_up(),    # If lane is above, do one step towards sky
                                        operand=None)

                return jax.lax.cond( # move_or_dont
                    is_on_correct_lane,
                    lambda _: dont_move_and_reset_lane_flag(),   # Enemy is on desired lane (allow new lane to be picked)
                    lambda _: move(),                            # Move enemy towards desired lane
                    operand=None
                )

            def get_next_pos():
                def pick_desired_lane():
                    is_in_top_lane = jnp.any(pos[1] == self.consts.TOP_LANES)           # If enemy is in the global top lane
                    is_in_middle_lane = jnp.any(pos[1] == self.consts.MIDDLE_LANES)     # If enemy is in the glocal middle lane

                    new_lane = self.consts.FRAMES_DEATH_ANIMATION_ENEMY + jnp.where( # Pick a valid lane for the enemy. (Pick one local lane from the global lane the enemy is on)
                        is_in_top_lane,
                        jax.random.choice(move_y_rng_key, self.consts.TOP_LANES).astype(jnp.float32),   # RNG FOR LANE PICK IS NOT FULLY RANDOM, LIKE IN REAL GAME. CHANGE ALL OCCURRENCES OF move_y_rng_keys[1] to move_y_rng_keys[i] FOR IT TO BE FULLY RANDOM
                        jnp.where(
                            is_in_middle_lane,
                            jax.random.choice(middle_lane_rng_key, self.consts.MIDDLE_LANES).astype(jnp.float32),
                            jax.random.choice(move_y_rng_key, self.consts.BOTTOM_LANES).astype(jnp.float32)  # If not in top or middle, enemy has to be in the bottom lane
                        )
                    )
                    return pos[1], new_lane


                should_switch = jax.random.bernoulli(middle_lane_rng_key, p=self.consts.ENEMY_LANE_SWITCH_PROBABILITY)
                return jax.lax.cond( # get_next_pos
                    jnp.logical_and(should_switch, is_on_correct_lane),
                    lambda _: pick_desired_lane(),  # Since enemy is on its desired lane and should_switch is triggered, we need to update the lane handler to the desired lane
                    lambda _: move_or_dont(),       # Move enemy if not on desired lane or don't move if on the desired lane
                    operand=None
                )

            (new_y, death_timer_or_lane_flag) = jax.lax.cond( # move_enemy_y
                jnp.logical_and((pos[3] > self.consts.FRAMES_DEATH_ANIMATION_ENEMY + 4), jnp.logical_and(is_active, move_y_is_in_range)),
                lambda _: get_next_pos(),           # If pos[3] is interpreted as the lane handler
                lambda _: dont_touch_position(),    # If pos[3] is interpreted as the death timer, also used for logic where the y position should not be changed
                operand=None
            )

            return jnp.array([pos[0], new_y, pos[2], death_timer_or_lane_flag], dtype=pos.dtype)

        def is_in_range_checker(pos: chex.Array) -> chex.Array:
            all_middle_trucks_x = jnp.array(
                [
                    truck_positions[1][0],
                    truck_positions[4][0],
                    truck_positions[7][0],
                    truck_positions[10][0],
                ]
            )

            # nearest_middle_truck = x-coordinate of middle truck closest to enemy with given pos
            distance_to_enemy = jnp.abs(all_middle_trucks_x - pos[0])
            min_index = jnp.argmin(distance_to_enemy)
            nearest_middle_truck = all_middle_trucks_x[min_index]

            # nearest_middle_truck_player = x-coordinate of middle truck closest to player
            distance_to_player = jnp.abs(all_middle_trucks_x - state_player_x + local_player_offset)
            min_index_player = jnp.argmin(distance_to_player)
            nearest_middle_truck_player = all_middle_trucks_x[min_index_player]

            return jnp.where(nearest_middle_truck == nearest_middle_truck_player, jnp.array(True), jnp.array(False))

        def process_enemy(current_pos, key, middle_lane_key, is_jet):                                                                      # Get current position
            enemy_is_in_range = is_in_range_checker(current_pos)                                                  # If jet is in "render distance". If not, it does not move
            new_pos = move_enemy_x(current_pos, is_jet, enemy_is_in_range)                               # Calculate new x position
            new_pos = move_enemy_y(new_pos, key, middle_lane_key, enemy_is_in_range)                           # Calculate new y position
            return new_pos

        # --Process jets --
        # Prepare rng keys for random jet movement TODO: randomization might need to be fixed
        keys_for_process_jet = jax.random.split(process_jet_rng, jet_positions.shape[0])  # Generate rng-key for every chopper there is. THIS IS NOT FULLY USED, SINCE MOVEMENT IS NOT FULLY RANDOM.
        middle_lane_jet_key = keys_for_process_jet[1]
        #new_jet_positions = jnp.zeros_like(jet_positions)   # for debugging purposes
        new_jet_positions = jax.vmap(
            lambda a, b: process_enemy(a, b, middle_lane_jet_key, jnp.array(True)),
            in_axes=(0, 0)
        )(jet_positions, keys_for_process_jet)

        # -- Process choppers --
        # Prepare rng keys for random jet movement TODO: randomization might need to be fixed
        keys_for_process_chopper = jax.random.split(process_chopper_rng, jet_positions.shape[0])  # Generate rng-key for every chopper there is. THIS IS NOT FULLY USED, SINCE MOVEMENT IS NOT FULLY RANDOM.
        middle_lane_chopper_key = keys_for_process_jet[1]
        #new_chopper_positions = jnp.zeros_like(chopper_positions)  # for debugging purposes
        new_chopper_positions = jax.vmap(
            lambda a, b: process_enemy(a, b, middle_lane_chopper_key, jnp.array(False)),
            in_axes=(0, 0)
        )(chopper_positions, keys_for_process_chopper)

        return new_jet_positions, new_chopper_positions, return_rng

    def update_entity_death(self, entity_array, death_timer, is_truck):
        def update_entity(entity):
            direction, timer = entity[2], entity[3]

            #Wenn Tod initialisiert (also noch aktiv) und timer > 0 & timer <= FRAMES_DEATH_ANIMATION, dann dekrementieren
            new_timer = jnp.where(jnp.logical_and(timer > 0, timer <= death_timer), timer - 1, timer)

            #Nach Ablauf von death_timer Enemy deaktivieren/entfernen
            new_entity = jnp.where(
                new_timer == 0,
                        jnp.where(
                            is_truck,
                            jnp.array([entity[0], entity[1], 0, 0], dtype=entity.dtype),
                            jnp.array([0, 0, 0, 0], dtype=entity.dtype)
                        ),
                entity.at[3].set(new_timer)
            )

            return new_entity

        return jax.vmap(update_entity)(entity_array)


    @partial(jax.jit, static_argnums=(0,))
    def initialize_truck_positions(self) -> chex.Array:     # TODO: change to vmap (via positioning array) if possible
        initial_truck_positions = jnp.zeros((self.consts.MAX_TRUCKS, 4))
        anchor = -748
        carry = (initial_truck_positions, anchor)

        def spawn_trucks(i, carry):
            truck_positions, anchor = carry

            anchor = jnp.where(
                i % 3 == 0,
                anchor + 248,
                anchor + 32,
            )
            truck_positions = truck_positions.at[i].set(jnp.array([anchor, 156, -1, self.consts.FRAMES_DEATH_ANIMATION_TRUCK + 1]))
            return truck_positions, anchor

        return jax.lax.fori_loop(0, 12, spawn_trucks, carry)[0]

    @partial(jax.jit, static_argnums=(0,))
    def step_truck_movement(
            self,
            truck_positions: chex.Array,
            state_player_x: chex.Array,
    ) -> chex.Array:

        def move_single_truck(truck_pos):
            movement_x = -1 * 0.5  # Geschwindigkeit 0.5 pro Frame, egal ob tot oder nicht, weil wir die Position noch für die enemy positions brauchen

            out_of_bounds = jnp.abs(state_player_x - truck_pos[0]) > 624

            new_x = jnp.where(
                out_of_bounds,
                truck_pos[0] + jnp.sign(state_player_x - truck_pos[0]) * 1248 + movement_x,
                truck_pos[0] + movement_x,
            )

            new_pos = jnp.array([new_x, truck_pos[1], truck_pos[2], truck_pos[3]])

            return new_pos

        return jax.vmap(move_single_truck)(truck_positions)


    @partial(jax.jit, static_argnums=(0,))
    def enemy_missiles_step(        # TODO: vmap
            self,
            jet_positions: chex.Array,  # (MAX_ENEMIES, 4)
            chopper_positions: chex.Array,  # (MAX_ENEMIES, 4)
            missile_states: chex.Array,  # (MAX_ENEMY_MISSILES, 4): [x, y, y_dir, did_split]
            rng: chex.PRNGKey,
    ) -> chex.Array:

        enemies = jnp.concat([jet_positions, chopper_positions], axis=0)

        def step_both_missiles(i, carry):
            missiles, key, eni = carry
            # Split key into spawn, split, speed, and next key
            key, key_spawn, key_split, key_speed = jax.random.split(key, 4)

            # Get current enemy
            current_enemy = enemies[eni]

            # Upper and lower missile
            missile_upper = missiles[i]
            missile_lower = missiles[i + 1]

            def maybe_spawn():
                def do_spawn():
                    # Coordinates of upper missile part
                    x_upper_spawn = current_enemy[0]
                    y_upper_spawn = current_enemy[1]

                    # Coordinates of lower missile part
                    x_lower_spawn = current_enemy[0]
                    y_lower_spawn = current_enemy[1] + 1

                    # Random Y Velocity
                    y_speed_spawn = jax.random.uniform(
                        key_speed,
                        (),
                        minval=-self.consts.ENEMY_MISSILE_MAXIMUM_Y_SPEED_BEFORE_SPLIT,
                        maxval=self.consts.ENEMY_MISSILE_MAXIMUM_Y_SPEED_BEFORE_SPLIT
                    )

                    # We also set the did_split flag to false
                    spawned_upper_missile = jnp.array([x_upper_spawn, y_upper_spawn, y_speed_spawn, 187.0], dtype=jnp.float32)
                    spawned_lower_missile = jnp.array([x_lower_spawn, y_lower_spawn, y_speed_spawn, 187.0], dtype=jnp.float32)

                    return spawned_upper_missile, spawned_lower_missile

                return jax.lax.cond(
                    jax.random.bernoulli(key_spawn, p=self.consts.ENEMY_MISSILE_SPAWN_PROBABILITY),
                    lambda _: do_spawn(), # Actually spawn
                    lambda _: (           # Leave dead
                        jnp.array([0.0, 0.0, 0.0, 187.0], dtype=jnp.float32),
                        jnp.array([0.0, 0.0, 0.0, 187.0], dtype=jnp.float32)
                    ),
                    operand=None
                )

            def do_step():
                x_upper_step, y_upper_step, y_upper_speed, did_split_upper_step = missile_upper
                x_lower_step, y_lower_step, y_lower_speed, did_split_lower_step = missile_lower

                def dont_split():
                    y_upper_step_inner = y_upper_step + y_upper_speed
                    y_lower_step_inner = y_lower_step + y_lower_speed
                    return (
                        y_upper_step_inner.astype(jnp.float32),
                        y_upper_speed.astype(jnp.float32),
                        y_lower_step_inner.astype(jnp.float32),
                        y_lower_speed.astype(jnp.float32),
                        187.0
                    )

                def do_split():
                    y_upper_speed_inner = jnp.array(self.consts.ENEMY_MISSILE_Y_SPEED_AFTER_SPLIT, dtype=jnp.float32)
                    y_lower_speed_inner = jnp.array(-self.consts.ENEMY_MISSILE_Y_SPEED_AFTER_SPLIT, dtype=jnp.float32)
                    y_upper_step_inner = y_upper_step + y_upper_speed_inner
                    y_lower_step_inner = y_lower_step + y_lower_speed_inner
                    return (
                        y_upper_step_inner.astype(jnp.float32),
                        y_upper_speed_inner,
                        y_lower_step_inner.astype(jnp.float32),
                        y_lower_speed_inner,
                        42.0
                    )

                split_condition = jnp.logical_and(
                    jax.random.bernoulli(key_split, p=self.consts.ENEMY_MISSILE_SPLIT_PROBABILITY),
                    jnp.logical_and(did_split_upper_step != 42.0, did_split_lower_step != 42.0)
                )

                y_upper_changed, y_upper_speed_changed, y_lower_changed, y_lower_speed_changed, flag = jax.lax.cond(
                    split_condition,
                    lambda _: do_split(),
                    lambda _: dont_split(),
                    operand=None
                )

                stepped_upper_missile = jnp.array([x_upper_step, y_upper_changed, y_upper_speed_changed, flag], dtype=jnp.float32)
                stepped_lower_missile = jnp.array([x_lower_step, y_lower_changed, y_lower_speed_changed, flag], dtype=jnp.float32)

                # Kill upper if out of bounds
                stepped_upper_missile = jnp.where(
                    jnp.logical_or(y_upper_changed < 44.0, y_upper_changed > 163.0),
                    jnp.array([0.0, 0.0, 0.0, 187.0], dtype=jnp.float32),
                    stepped_upper_missile,
                )

                # Kill lower if out of bounds
                stepped_lower_missile = jnp.where(
                    jnp.logical_or(y_lower_changed < 44.0, y_lower_changed > 163.0),
                    jnp.array([0.0, 0.0, 0.0, 187.0], dtype=jnp.float32),
                    stepped_lower_missile
                )

                return stepped_upper_missile, stepped_lower_missile

            # Check if missile is "alive"
            upper_dead = jnp.all(missile_upper == jnp.array([0.0, 0.0, 0.0, 187.0], dtype=jnp.float32))
            lower_dead = jnp.all(missile_lower == jnp.array([0.0, 0.0, 0.0, 187.0], dtype=jnp.float32))

            updated_missile_upper, updated_missile_lower = jax.lax.cond(
                jnp.logical_and(upper_dead, lower_dead),
                lambda _: maybe_spawn(),
                lambda _: do_step(),
                operand=None
            )

            missiles = missiles.at[i].set(updated_missile_upper)
            missiles = missiles.at[i + 1].set(updated_missile_lower)

            return missiles, key

        def step_even(i, carry):
            a, b = carry
            carry = a, b, i
            return step_both_missiles(i * 2, carry)

        updated, _ = jax.lax.fori_loop(
            0, enemies.shape[0], step_even, (missile_states, rng)
        )
        return updated


    @partial(jax.jit, static_argnums=(0,))
    def player_missile_step(
            self,
            state: ChopperCommandState,
            curr_player_x,
            curr_player_y,
            action: chex.Array,
    ):
        fire = jnp.any(
            jnp.array([
                action == Action.FIRE,
                action == Action.UPRIGHTFIRE,
                action == Action.UPLEFTFIRE,
                action == Action.DOWNFIRE,
                action == Action.DOWNRIGHTFIRE,
                action == Action.DOWNLEFTFIRE,
                action == Action.RIGHTFIRE,
                action == Action.LEFTFIRE,
                action == Action.UPFIRE,
            ])
        )

        missile_y = curr_player_y + 6
        cooldown = jnp.maximum(state.player_missile_cooldown - 1, 0)

        def try_spawn(missiles): # TODO: rewrite
            def body(i, carry):
                missiles, did_spawn = carry
                missile = missiles[i]
                free = missile[2] == 0  # direction == 0 -> inactive
                should_spawn = jnp.where(self.consts.MAX_PLAYER_MISSILES > 1,
                                         jnp.logical_and(free, jnp.logical_not(did_spawn)),
                                         jnp.array(True))

                spawn_x = jnp.where(
                    state.player_facing_direction == -1,
                    curr_player_x - self.consts.PLAYER_MISSILE_WIDTH,
                    curr_player_x + self.consts.PLAYER_SIZE[0],
                )

                new_missile = jnp.array([
                    spawn_x, # x
                    missile_y, # y
                    state.player_facing_direction, # dir
                    spawn_x # x_spawn
                ], dtype=jnp.int32)

                updated_missile = jnp.where(should_spawn, new_missile, missile)
                missiles = missiles.at[i].set(updated_missile)
                return missiles, jnp.logical_or(did_spawn, should_spawn)

            return jax.lax.fori_loop(0, missiles.shape[0], body, (missiles, False))

        def spawn_if_possible(missiles):
            def do_spawn(_):
                return try_spawn(missiles)
            def skip_spawn(_):
                return missiles, False
            return jax.lax.cond(jnp.logical_and(jnp.logical_and(fire, state.pause_timer > self.consts.DEATH_PAUSE_FRAMES), cooldown == 0), do_spawn, skip_spawn, operand=None)

        def update_missile(missile):
            exists = missile[2] != 0
            new_x = missile[0] + missile[2] * self.consts.MISSILE_SPEED + state.player_velocity_x

            updated = jnp.array([
                new_x,        # updated x
                missile[1],   # y stays
                missile[2],   # direction stays
                missile[3]    # x_spawn stays
            ], dtype=jnp.int32)

            chopper_pos = (self.consts.WIDTH // 2) - 8 + state.local_player_offset + (state.player_velocity_x * self.consts.DISTANCE_WHEN_FLYING)
            left_bound = state.player_x - chopper_pos - self.consts.PLAYER_MISSILE_WIDTH
            right_bound = state.player_x + (self.consts.WIDTH - chopper_pos)

            out_of_bounds = jnp.logical_or(updated[0] < left_bound, updated[0] > right_bound)
            return jnp.where(jnp.logical_and(exists, ~out_of_bounds), updated, jnp.array([0, 0, 0, 0], dtype=jnp.int32))

        updated_missiles = jax.vmap(update_missile)(state.player_missile_positions)
        # jax.debug.print("{}", updated_missiles)
        updated_missiles, did_spawn = spawn_if_possible(updated_missiles)
        new_cooldown = jnp.where(did_spawn, self.consts.MISSILE_COOLDOWN_FRAMES, cooldown)

        return updated_missiles, new_cooldown


    @partial(jax.jit, static_argnums=(0,))
    def player_step(
        self,
        state: ChopperCommandState,
        action: chex.Array,
    ) -> tuple[chex.Array, chex.Array, chex.Array, chex.Array, chex.Array]:
        # Bewegungsrichtung bestimmen
        up = jnp.isin(action, jnp.array([
            Action.UP,
            Action.UPRIGHT,
            Action.UPLEFT,
            Action.UPFIRE,
            Action.UPRIGHTFIRE,
            Action.UPLEFTFIRE
        ]))
        down = jnp.isin(action, jnp.array([
            Action.DOWN,
            Action.DOWNRIGHT,
            Action.DOWNLEFT,
            Action.DOWNFIRE,
            Action.DOWNRIGHTFIRE,
            Action.DOWNLEFTFIRE
        ]))
        left = jnp.isin(action, jnp.array([
            Action.LEFT,
            Action.UPLEFT,
            Action.DOWNLEFT,
            Action.LEFTFIRE,
            Action.UPLEFTFIRE,
            Action.DOWNLEFTFIRE
        ]))
        right = jnp.isin(action, jnp.array([
            Action.RIGHT,
            Action.UPRIGHT,
            Action.DOWNRIGHT,
            Action.RIGHTFIRE,
            Action.UPRIGHTFIRE,
            Action.DOWNRIGHTFIRE
        ]))


        # Ziel-Beschleunigung basierend auf Eingabe
        accel_x = jnp.where(right, self.consts.ACCEL, jnp.where(left, -self.consts.ACCEL, 0.0))

        # Direction player is facing
        new_player_facing_direction = jnp.where(right, 1, jnp.where(left, -1, state.player_facing_direction))

        # Neue Geschwindigkeit berechnen und begrenzen
        velocity_x = state.player_velocity_x + accel_x
        velocity_x = jnp.clip(velocity_x, -self.consts.MAX_VELOCITY, self.consts.MAX_VELOCITY)

        # Falls keine Eingabe: langsamer werden (Friction)
        velocity_x = jnp.where(~(left | right), velocity_x * (1.0 - self.consts.FRICTION), velocity_x)

        # Neue X-Position (global!)
        player_x = state.player_x + velocity_x

        # Y-Position berechnen (sofortige Reaktion)
        delta_y = jnp.where(up, -1, jnp.where(down, 1, 0))
        player_y = jnp.clip(state.player_y + delta_y, self.consts.PLAYER_BOUNDS[1][0], self.consts.PLAYER_BOUNDS[1][1])

        # "Momentum" berechnen für Offset von der Mitte aus
        new_player_offset = jnp.where(new_player_facing_direction == 1, state.local_player_offset - self.consts.LOCAL_PLAYER_OFFSET_SPEED, state.local_player_offset + self.consts.LOCAL_PLAYER_OFFSET_SPEED)
        new_player_offset = jnp.asarray(new_player_offset, dtype=jnp.int32)

        new_player_offset = jnp.clip(new_player_offset, -60, 60)

        return player_x, player_y, velocity_x, new_player_offset, new_player_facing_direction

    @partial(jax.jit, static_argnums=(0,))
    def lives_step(
            self,
            player_collision: chex.Array,
            current_score: jnp.int32,
            save_lives: jnp.int32,
    ) -> tuple[jnp.int32, jnp.int32]:

        current_score = jnp.where(current_score == 0, 1, current_score)
        num_to_add = jnp.where(player_collision, -1, 0)

        num_to_add = jnp.where((current_score // 10000) > save_lives, num_to_add + 1, num_to_add)
        new_save_lives = jnp.where((current_score // 10000) > save_lives, save_lives + 1, save_lives)

        return num_to_add, new_save_lives

    @partial(jax.jit, static_argnums=(0,))
    def reset(self, key: jax.random.PRNGKey = jax.random.PRNGKey(time.time_ns() % (2**32))) -> Tuple[ChopperCommandObservation, ChopperCommandState]:
        """Initialize game state"""

        new_key0, key0 = jax.random.split(key, 2)
        jet_positions, chopper_positions = self.initialize_enemy_positions(key0)
        initial_enemy_missile_positions = jnp.full((self.consts.MAX_ENEMY_MISSILES, 4), jnp.array([0, 0, 0, 187], dtype=jnp.float32))

        # FOR EXPLANATION OF FIELDS SEE ChopperCommandState CLASS
        reset_state = ChopperCommandState(
            player_x=jnp.array(self.consts.PLAYER_START_X).astype(jnp.float32),             # Initial horizontal spawn position of the player in world space. Sets where the chopper starts.
            player_y=jnp.array(self.consts.PLAYER_START_Y).astype(jnp.int32),               # Initial vertical spawn position of the player. Ensures the chopper appears above ground level.
            player_velocity_x=jnp.array(0).astype(jnp.float32),                 # Player starts at rest horizontally — no momentum on the first frame.
            local_player_offset=jnp.array(50).astype(jnp.float32),              # Initial screen offset. This is for the no_move_pause animation when starting the game and respawning.
            player_facing_direction=jnp.array(1).astype(jnp.int32),             # # Player begins facing right (1).
            score=jnp.array(0).astype(jnp.int32),                               # Game always starts with a score of 0.
            lives=jnp.array(3).astype(jnp.int32),                               # Standard number of starting lives.
            save_lives=jnp.array(0).astype(jnp.int32),                          # Player starts with no lives granted for every 10000 points reached
            truck_positions=self.initialize_truck_positions().astype(jnp.float32),   # Trucks are initialized with predefined starting positions and inactive death timers.
            jet_positions=jet_positions,                                        # Jets are initialized with predefined starting positions and inactive death timers.
            chopper_positions=chopper_positions,                                # Choppers are initialized with predefined starting positions and inactive death timers.
            enemy_missile_positions=initial_enemy_missile_positions,            # All enemy missile entries are coded as "dead": [0.0, 0.0, 0.0, 187.0], meaning no missiles are in play at start.
            player_missile_positions=jnp.zeros((self.consts.MAX_PLAYER_MISSILES, 4)),       # All player missile slots are zeroed out; meaning no missiles are in play at start.
            player_missile_cooldown=jnp.array(0),                               # Cooldown timer is 0, so the player is allowed to shoot immediately.
            player_collision=jnp.array(False),                                  # Player has not collided with anything on game start.
            step_counter=jnp.array(0).astype(jnp.int32),                        # Frame counter starts from 0.
            pause_timer=jnp.array(self.consts.DEATH_PAUSE_FRAMES + 2).astype(jnp.int32),    # The game starts in the no_move_pause (DEATH_PAUSE_FRAMES + 2) to allow for visual startup or intro.
            rng_key=new_key0,                                            # Pseudo random number generator seed key, based on current time and initial key used.
            obs_stack=jnp.zeros((self.frame_stack_size, self.obs_size)),        # Observation stack starts empty (zeros). Used for agent state.
            difficulty=jnp.array(self.consts.GAME_DIFFICULTY).astype(jnp.float32),          # difficulty of game
            enemy_speed=jnp.array(0).astype(jnp.float32),                       # enemy_speed which is 0 on start
        )

        initial_obs = self._get_observation(reset_state)

        def expand_and_copy(x):
            x_expanded = jnp.expand_dims(x, axis=0)
            return jnp.concatenate([x_expanded] * self.frame_stack_size, axis=0)

        # Apply transformation to each leaf in the pytree
        initial_obs = jax.tree.map(expand_and_copy, initial_obs)
        reset_state = reset_state._replace(obs_stack=initial_obs)
        return initial_obs, reset_state


    @partial(jax.jit, static_argnums=(0,))
    def step(
            self, state: ChopperCommandState, action: chex.Array
    ) -> Tuple[ChopperCommandState, ChopperCommandObservation, jnp.ndarray, bool, ChopperCommandInfo]:

        previous_state = state

        #The normal_game_state is one step (e.g. one frame) of the normally ongoing game
        def get_normal_game_state(state, action):
            # --------------- RANDOM NUMBER GENERATION ---------------

            rng0 = state.rng_key
            rng1, key0, key1 = jax.random.split(rng0, 3)

            # --------------- POSITION UPDATES ---------------

            # Update player position
            (
                new_player_x,
                new_player_y,
                new_player_velocity_x,
                new_local_player_offset,
                new_player_facing_direction
            ) = self.player_step(
                state, action
            )

            # Update jet and chopper positions
            new_jet_positions, new_chopper_positions, new_rng_key = self.step_enemy_movement(
                state.truck_positions,
                state.jet_positions,
                state.chopper_positions,
                key0,
                state.player_x,
                state.local_player_offset,  # Needed to find the nearest enemy fleet correctly
                state.difficulty,
                state.enemy_speed,
            )

            # Update truck positions
            new_truck_positions = (
                self.step_truck_movement(
                    state.truck_positions,
                    state.player_x,
                )
            )

            # Update enemy missile positions
            new_enemy_missile_positions = self.enemy_missiles_step(
                new_jet_positions, new_chopper_positions, state.enemy_missile_positions, key1
            )

            # Update player missile positions
            new_player_missile_positions, new_cooldown = self.player_missile_step(
                state, state.player_x, state.player_y, action
            )

            # --------------- COLLISION UPDATES ---------------

            on_screen_chopper_position = (self.consts.WIDTH // 2) - 8 + new_local_player_offset + (new_player_velocity_x * self.consts.DISTANCE_WHEN_FLYING)

            # Check player missile collisions with jets
            (
                new_jet_positions,
                new_player_missile_position,
                score_to_add_jet,
            ) = self.check_missile_collisions(
                new_player_missile_positions,
                new_jet_positions,
                on_screen_chopper_position,
                new_player_x,
                self.consts.JET_SIZE
            )

            # Check player missile collisions with choppers
            (
                new_chopper_positions,
                new_player_missile_position,
                score_to_add_chopper,
            ) = self.check_missile_collisions(
                new_player_missile_positions,
                new_chopper_positions,
                on_screen_chopper_position,
                new_player_x,
                self.consts.CHOPPER_SIZE
            )

            #jax.debug.print("{a}, {b}", a=new_jet_positions[:,0], b=new_chopper_positions[:,0])



            # Check player collision with jets
            player_collision_jet, player_collision_new_jet_pos = self.check_player_collision_entity(
                new_player_x,
                new_player_y,
                new_player_velocity_x,
                new_jet_positions,
                self.consts.JET_SIZE,
                self.consts.FRAMES_DEATH_ANIMATION_ENEMY,
            )
            new_jet_positions = player_collision_new_jet_pos

            # Check player collision with choppers
            player_collision_chopper, player_collision_new_chopper_pos = self.check_player_collision_entity(
                new_player_x,
                new_player_y,
                new_player_velocity_x,
                new_chopper_positions,
                self.consts.CHOPPER_SIZE,
                self.consts.FRAMES_DEATH_ANIMATION_ENEMY,
            )
            new_chopper_positions = player_collision_new_chopper_pos

            # Check player collision with trucks
            player_collision_truck, player_collision_new_truck_pos = self.check_player_collision_entity(
                new_player_x,
                new_player_y,
                new_player_velocity_x,
                new_truck_positions,
                self.consts.TRUCK_SIZE,
                self.consts.FRAMES_DEATH_ANIMATION_TRUCK,
            )
            new_truck_positions = player_collision_new_truck_pos

            # Check player collision with enemy missiles
            player_collision_enemy_missile, player_collision_new_missile_pos = self.check_player_collision_entity(
                new_player_x,
                new_player_y,
                new_player_velocity_x,
                new_enemy_missile_positions,
                self.consts.ENEMY_MISSILE_SIZE,
                0,
            )
            new_enemy_missile_positions = player_collision_new_missile_pos

            # Check enemy missiles collision with trucks
            mis_tru_collision_truck_positions, mis_tru_collision_missile_positions = self.check_missile_truck_collisions(
                new_truck_positions,
                new_enemy_missile_positions,
                self.consts.TRUCK_SIZE,
                self.consts.ENEMY_MISSILE_SIZE
            )

            new_truck_positions = jnp.where(self.consts.ENABLE_ENEMY_MISSILE_TRUCK_COLLISION, mis_tru_collision_truck_positions, new_truck_positions)
            new_enemy_missile_positions = mis_tru_collision_missile_positions

            # If player collided with anything
            player_collision = jnp.logical_or(
                player_collision_jet,
                jnp.logical_or(
                    player_collision_chopper,
                    jnp.logical_or(
                        player_collision_truck,
                        player_collision_enemy_missile
                    )
                )
            )
            player_collision = jnp.where(self.consts.ENABLE_PLAYER_COLLISION,
                                         player_collision,
                                         jnp.array(False)
                                         )

            # --------------- DEATH UPDATES ---------------

            # Update enemy death
            new_chopper_positions = self.update_entity_death(new_chopper_positions, self.consts.FRAMES_DEATH_ANIMATION_ENEMY,jnp.array(False))
            new_jet_positions = self.update_entity_death(new_jet_positions, self.consts.FRAMES_DEATH_ANIMATION_ENEMY, jnp.array(False))
            new_truck_positions = self.update_entity_death(new_truck_positions, self.consts.FRAMES_DEATH_ANIMATION_TRUCK,jnp.array(True))

            # --------------- SCORE AND LIFE UPDATES ---------------

            # Update score with collision points
            new_score = state.score  # Get current score
            new_score = new_score + score_to_add_chopper + score_to_add_jet  # Add scores from enemy kills by player missile
            new_score = jnp.where(player_collision_jet, new_score + self.consts.SCORE_PER_JET_KILL,new_score)  # Add scores from enemy kills by collision with jet
            new_score = jnp.where(player_collision_chopper, new_score + self.consts.SCORE_PER_CHOPPER_KILL,new_score)  # Add scores from enemy kills by collision with chopper
            new_score = jnp.minimum(new_score, 999999)  # Score cannot be greater than 999999

            # Update lives if player collides with an enemy or enemy missile and add one life for every 10000 points
            new_lives_to_add, new_save_lives = self.lives_step(player_collision, state.score, state.save_lives)
            new_lives = state.lives + new_lives_to_add

            # --------------- STEP COUNT ---------------

            # Update step counter
            new_step_counter = state.step_counter + 1

            # --------------- CREATE THE NORMAL RETURNED STATE ---------------

            inner_normal_returned_state = ChopperCommandState(
                player_x=new_player_x,
                player_y=new_player_y,
                player_velocity_x=new_player_velocity_x,
                local_player_offset=new_local_player_offset,
                player_facing_direction=new_player_facing_direction,
                score=new_score,
                lives=new_lives,
                save_lives=new_save_lives,
                truck_positions=new_truck_positions,
                jet_positions=new_jet_positions,
                chopper_positions=new_chopper_positions,
                enemy_missile_positions=new_enemy_missile_positions,
                player_missile_positions=new_player_missile_position,
                player_missile_cooldown=new_cooldown,
                player_collision=player_collision,
                step_counter=new_step_counter,
                pause_timer=state.pause_timer,
                rng_key=new_rng_key,
                obs_stack=state.obs_stack,  # Include obs_stack in the state
                difficulty=state.difficulty,
                enemy_speed=state.enemy_speed,
            )

            return inner_normal_returned_state

        # The death_pause is the pause that occurs right after the chopper died
        def get_death_pause_state(state, normal_state, action):
            in_pause = jnp.logical_and(state.pause_timer <= self.consts.DEATH_PAUSE_FRAMES, state.pause_timer > 0)

            # pause counter
            new_pause_timer = jnp.where(in_pause, state.pause_timer - 1, state.pause_timer)
            # Freeze pause counter if player has no lives left
            new_pause_timer = jnp.where(state.lives == 0, jnp.maximum(new_pause_timer, 1), new_pause_timer)

            all_enemies_dead = jnp.logical_and(
                jnp.all(state.jet_positions == 0),
                jnp.all(state.chopper_positions == 0)
            )

            # Normal truck step
            def death_pause_truck_step_normal():
                # truck deaths
                temp_truck_positions = (
                    self.step_truck_movement(
                        normal_state.truck_positions,
                        normal_state.player_x,
                    )
                )

                updated_truck_death_timers = temp_truck_positions[:, 3]  # neue Timer
                return state.truck_positions.at[:, 3].set(updated_truck_death_timers), 0

            # Truck reset animation and score animation
            def death_pause_truck_step_give_points():
                # Starts killing trucks at the truck that is the furthest to the left
                start_idx = 6

                elapsed = self.consts.DEATH_PAUSE_FRAMES - state.pause_timer
                frames_per_kill = self.consts.DEATH_PAUSE_FRAMES // self.consts.MAX_TRUCKS

                num_remove_now = jnp.clip(elapsed // frames_per_kill, 0, self.consts.MAX_TRUCKS)        # Number of trucks to remove in this frame
                num_remove_prev = jnp.clip((elapsed - 1) // frames_per_kill, 0, self.consts.MAX_TRUCKS) # Number of trucks that were removed last frame

                id = jnp.arange(self.consts.MAX_TRUCKS)
                rel_idx = jnp.mod(id - start_idx, self.consts.MAX_TRUCKS)

                # Mask: Who should be dead now? Who was already dead?
                kill_mask_now = rel_idx < num_remove_now
                kill_mask_prev = rel_idx < num_remove_prev

                # Killed in this frame
                newly_killed = jnp.logical_and(kill_mask_now, jnp.logical_not(kill_mask_prev))

                directions = state.truck_positions[:, 2]
                alive_before = directions != 0

                # Only give points if truck was alive
                valid_kill = jnp.logical_and(newly_killed, alive_before)

                # Give points
                num_valid_kills = jnp.sum(valid_kill)
                add_to_score = num_valid_kills * self.consts.SCORE_PER_TRUCK_ALIVE

                # Delete trucks
                zero_truck = jnp.zeros_like(state.truck_positions)
                new_trucks = jnp.where(kill_mask_now[:, None], zero_truck, state.truck_positions)

                return new_trucks, add_to_score

            # Decides if trucks should be all killed and given points for or just rendered as the death_animation (in the render function)
            new_truck_positions, new_add_to_score = jax.lax.cond(all_enemies_dead,
                                               lambda _: death_pause_truck_step_give_points(),
                                               lambda _:death_pause_truck_step_normal(),
                                               operand=None
                                               )
            new_score = state.score + new_add_to_score




            # Enemy deaths
            temp_jet_positions, temp_chopper_positions, _ = (
                self.step_enemy_movement(
                    normal_state.truck_positions,
                    normal_state.jet_positions,
                    normal_state.chopper_positions,
                    normal_state.rng_key,
                    normal_state.player_x,
                    normal_state.local_player_offset,
                    normal_state.difficulty,
                    normal_state.enemy_speed,
                )
            )

            updated_jet_death_timers = temp_jet_positions[:, 3]  # neue Timer
            updated_chopper_death_timers = temp_chopper_positions[:, 3]  # neue Timer

            new_jet_positions_pause = state.jet_positions.at[:, 3].set(updated_jet_death_timers)
            new_chopper_positions_pause = state.chopper_positions.at[:, 3].set(updated_chopper_death_timers)


            new_player_missile_positions, new_cooldown = self.player_missile_step(
                normal_state, normal_state.player_x, normal_state.player_y, action
            )

            new_player_missile_positions = new_player_missile_positions.astype(jnp.float32)

            new_enemy_missile_positions = jnp.full((self.consts.MAX_ENEMY_MISSILES, 4), jnp.array([0, 0, 0, 187], dtype=jnp.float32))

            # Things that have to be updated in the pause
            # truck_positions[i][3]     - this is required for rendering truck death animation while paused
            # jet_positions[i][3]       - this is required for rendering jet death animation while paused
            # chopper_positions[i][3]   - this is required for rendering chopper death animation while paused
            # enemy_missile_positions   - this is required to delete all enemy missiles instantly when player dies
            # player_missile_positions  - this is required to let player missile travel while paused
            # player_missile_cooldown   - this is a dependency for player_missile_positions
            # pause_timer               - this is required for ending the pause
            paused_state = state._replace(
                score=new_score,
                truck_positions=new_truck_positions,
                jet_positions=new_jet_positions_pause,
                chopper_positions=new_chopper_positions_pause,
                enemy_missile_positions=new_enemy_missile_positions,
                player_missile_positions=new_player_missile_positions,
                player_missile_cooldown=new_cooldown,
                pause_timer=new_pause_timer,
            )

            return paused_state

        # The no_move_pause is the pause between the pause that occurs instantly after death and the first input
        def get_no_move_pause_state(state, action):
            no_input = jnp.isin(action, Action.NOOP)

            on_screen_position = (self.consts.WIDTH // 2) - 8 + state.local_player_offset + (state.player_velocity_x * self.consts.DISTANCE_WHEN_FLYING)
            chopper_at_desired_point = on_screen_position <= self.consts.ALLOW_MOVE_OFFSET

            # Things that have to be updated in the no_move_pause
            # local_player_offset - this is required for moving the chopper to the left of the screen, since we are not calling player_step anymore
            # pause_timer         - this is required for keeping the game paused until chopper is at the desired location and an input is made
            no_move_state = state._replace(
                local_player_offset=jnp.where(chopper_at_desired_point,
                                              state.local_player_offset,
                                              state.local_player_offset - self.consts.LOCAL_PLAYER_OFFSET_SPEED
                                              ),
                pause_timer=jnp.where(jnp.logical_and(chopper_at_desired_point, jnp.logical_not(no_input)),
                                      jnp.array(self.consts.DEATH_PAUSE_FRAMES + 1),
                                      jnp.array(state.pause_timer) #Stay in no_move_pause
                                      )
            )

            return no_move_state


        # Calculate all possible next states
        normal_state = get_normal_game_state(state, action)
        death_pause_state = get_death_pause_state(state, normal_state, action)
        no_move_state = get_no_move_pause_state(state, action)

        # dtype-Mismatch fix
        normal_state = jax.tree.map(
            lambda new, old: new.astype(old.dtype),
            normal_state,
            state
        )

        # dtype-Mismatch fix
        death_pause_state = jax.tree.map(
            lambda new, old: new.astype(old.dtype),
            death_pause_state,
            state,
        )

        # dtype-Mismatch fix
        no_move_state = jax.tree.map(
            lambda new, old: new.astype(old.dtype),
            no_move_state,
            state
        )

        # Pick correct state
        step_state = jax.lax.cond(
            state.pause_timer <= self.consts.DEATH_PAUSE_FRAMES, #Pick the death_pause if Pause was initiated
            lambda _: death_pause_state,
            lambda _: normal_state,
            operand=None
        )

        step_state = jax.lax.cond(
            state.pause_timer == self.consts.DEATH_PAUSE_FRAMES + 2, #Pick the no_move_pause if no move pause was initiated
            lambda _: no_move_state,
            lambda _: step_state,
            operand=None
        )

        # Soft- und Hard-Reset-Logik
        # Soft-Reset (früher war das normal_game_step(get_prev_fields=True))
        soft_reset_state = death_pause_state
        soft_reset_state = jax.lax.cond(
            state.pause_timer == self.consts.DEATH_PAUSE_FRAMES + 2,
            lambda _: no_move_state,
            lambda _: soft_reset_state,
            operand=None
        )
        # Hard-Reset von Env.reset()
        #new_reset_rng, key = jax.random.split(state.rng_key, 2) #TODO: Implement enemies having new positions when respawning. <--- this (the commented code) doesnt really work...
        _, hard_reset_state = self.reset()

        # Merge von Todes-Timern in den Hard-Reset-Zuständen
        def merge_column(reset_pos, other_pos, col_idx):
            def replace_col(row_reset, row_other):
                return row_reset.at[col_idx].set(row_other[col_idx])
            return jax.vmap(replace_col)(reset_pos, other_pos)

        merged_jet_pos = merge_column(hard_reset_state.jet_positions, soft_reset_state.jet_positions, 3)
        merged_chop_pos = merge_column(hard_reset_state.chopper_positions, soft_reset_state.chopper_positions, 3)
        merged_truck_pos = merge_column(hard_reset_state.truck_positions, soft_reset_state.truck_positions, 3)

        # Erstelle respawn_state
        respawn_state = hard_reset_state._replace(
            # hard Resets
            player_x=hard_reset_state.player_x,
            # soft Resets
            score=soft_reset_state.score,
            lives=soft_reset_state.lives,
            save_lives=soft_reset_state.save_lives,
            jet_positions=merged_jet_pos,
            chopper_positions=merged_chop_pos,
            truck_positions=merged_truck_pos,
            enemy_speed=soft_reset_state.enemy_speed,
        )

        # Pause-Initialisierung und Update
        just_died = jnp.logical_and(
            step_state.player_collision,
            step_state.pause_timer > self.consts.DEATH_PAUSE_FRAMES
        )
        all_enemies_dead = jnp.logical_and(
            jnp.all(step_state.jet_positions == 0),
            jnp.all(step_state.chopper_positions == 0)
        )
        initial_dead_pause = jnp.logical_and(all_enemies_dead, step_state.pause_timer > self.consts.DEATH_PAUSE_FRAMES)

        respawn_state = respawn_state._replace(
            jet_positions=jnp.where(
                jnp.logical_and(all_enemies_dead, step_state.pause_timer == 0),
                hard_reset_state.jet_positions,
                respawn_state.jet_positions
            ),
            chopper_positions=jnp.where(
                jnp.logical_and(all_enemies_dead, step_state.pause_timer == 0),
                hard_reset_state.chopper_positions,
                respawn_state.chopper_positions
            ),
            truck_positions=jnp.where(
                jnp.logical_and(all_enemies_dead, step_state.pause_timer == 0),
                hard_reset_state.truck_positions,
                respawn_state.truck_positions
            ),
            enemy_speed=jnp.where(
                jnp.logical_and(all_enemies_dead, step_state.pause_timer == 0),
                soft_reset_state.enemy_speed + 0.5,
                respawn_state.enemy_speed
            )
        )

        step_state = step_state._replace(
            pause_timer=jnp.where(
                jnp.logical_or(just_died, initial_dead_pause),
                jnp.array(self.consts.DEATH_PAUSE_FRAMES),
                step_state.pause_timer
            )
        )

        # Weitermachen oder Respawn
        step_state = jax.lax.cond(
            state.pause_timer != 0,
            lambda _: step_state,
            lambda _: respawn_state,
            operand=None
        )

        # Observation, Reward, Done, Info
        observation = self._get_observation(step_state)
        done = self._get_done(step_state)
        env_reward = self._get_env_reward(previous_state, step_state)
        all_rewards = self._get_all_rewards(previous_state, step_state)
        info = self._get_info(step_state, all_rewards)

        # Obs-Stack aktualisieren
        new_obs_stack = jax.tree.map(
            lambda stack, obs: jnp.concatenate([stack[1:], jnp.expand_dims(obs, 0)], axis=0),
            step_state.obs_stack,
            observation
        )
        step_state = step_state._replace(obs_stack=new_obs_stack)

        return new_obs_stack, step_state, env_reward, done, info


class ChopperCommandRenderer(JAXGameRenderer):
    def __init__(self, consts: ChopperCommandConstants = None):
        super().__init__()
        self.consts = consts or ChopperCommandConstants()

    @partial(jax.jit, static_argnums=(0,))
    def render(self, state):
        # Local position of player on screen
        chopper_position = (self.consts.WIDTH // 2) + state.local_player_offset + (state.player_velocity_x * self.consts.DISTANCE_WHEN_FLYING) - (self.consts.PLAYER_SIZE[0] // 2) # (WIDTH // 2) - 8 = Heli mittig platzieren, state.local_player_offset = ob Heli links oder rechts auf Bildschirm, state.player_velocity_x * DISTANCE_WHEN_FLYING = Bewegen von Heli richtung Mitte wenn er fliegt

        # Bildschirmmitte relativ zur Scrollrichtung des Spielers
        static_center_x_jet = (self.consts.WIDTH // 2) + state.local_player_offset - (self.consts.JET_SIZE[0] // 2)
        static_center_x_chopper = (self.consts.WIDTH // 2) + state.local_player_offset - (self.consts.CHOPPER_SIZE[0] // 2)
        static_center_x_truck = (self.consts.WIDTH // 2) + state.local_player_offset - (self.consts.TRUCK_SIZE[0] // 2)

        #Initialisierung
        raster = jnp.zeros((self.consts.HEIGHT, self.consts.WIDTH,  3))

        # Render Background
        frame_idx = jnp.asarray(state.local_player_offset + (-state.player_x % self.consts.WIDTH), dtype=jnp.int32) #local_player_offset = ob Heli links oder rechts auf Bildschirm ist, -state.player_x % WIDTH = Scrollen vom Hintergrund
        frame_bg = jru.get_sprite_frame(SPRITE_BG, frame_idx)

        raster = jru.render_at(raster, 0, 0, frame_bg)

        frame_friendly_truck = jru.get_sprite_frame(SPRITE_FRIENDLY_TRUCK, state.step_counter)

        def render_truck(i, raster_base):
            death_timer = state.truck_positions[i][3]
            direction = state.truck_positions[i][2]

            #am Leben: direction != 0 UND death_timer > FRAMES_DEATH_ANIMATION_TRUCK
            is_alive = jnp.logical_and(direction != 0,
                                       death_timer > self.consts.FRAMES_DEATH_ANIMATION_TRUCK)

            #in der Todes-Animation: direction != 0 UND 0 < death_timer <= FRAMES_DEATH_ANIMATION_TRUCK
            is_dying = jnp.logical_and(
                direction != 0,
                jnp.logical_and(death_timer <= self.consts.FRAMES_DEATH_ANIMATION_TRUCK,
                                death_timer > 0)
            )

            #flicker-Phase (nur relevant wenn is_dying)
            in_flicker_on = (death_timer % self.consts.TRUCK_FLICKER_RATE) < (self.consts.TRUCK_FLICKER_RATE // 2)

            # Render-Logik: immer anzeigen, solange ALIVE oder (DYING & flicker_on)
            should_render = jnp.logical_or(is_alive,
                                           jnp.logical_and(is_dying,
                                                           in_flicker_on))

            truck_screen_x = state.truck_positions[i][0] - state.player_x + static_center_x_truck
            truck_screen_y = state.truck_positions[i][1]

            return jax.lax.cond(
                should_render,
                lambda r: jru.render_at(
                    r,
                    truck_screen_x,
                    truck_screen_y,
                    frame_friendly_truck,
                    flip_horizontal=(state.truck_positions[i][2] == -1),
                ),
                lambda r: r,
                raster_base,
            )

        raster = jax.lax.fori_loop(0, self.consts.MAX_TRUCKS, render_truck, raster)

        # -- JET Rendering --
        frame_enemy_jet = jru.get_sprite_frame(SPRITE_ENEMY_JET, state.step_counter)

        def render_enemy_jet(i, raster_base):
            death_timer = state.jet_positions[i][3]

            should_render = jnp.logical_and(state.jet_positions[i][2] != 0, death_timer > 0)

            jet_screen_x = state.jet_positions[i][0] - state.player_x + static_center_x_jet
            jet_screen_y = state.jet_positions[i][1]

            phase0 = death_timer > (2 * self.consts.FRAMES_DEATH_ANIMATION_ENEMY) // 3
            phase1 = jnp.logical_and(
                death_timer <= (2 * self.consts.FRAMES_DEATH_ANIMATION_ENEMY) // 3,
                death_timer > self.consts.FRAMES_DEATH_ANIMATION_ENEMY // 3
            )
            death_sprite = jnp.where(
                phase0, ENEMY_CHOPPER_DEATH_1,
                jnp.where(phase1, ENEMY_CHOPPER_DEATH_2, ENEMY_CHOPPER_DEATH_3)
            )

            def render_true(r):
                # je nach death_timer richtigen Sprite rendern
                return jax.lax.cond(
                    death_timer <= self.consts.FRAMES_DEATH_ANIMATION_ENEMY,
                    # Wenn in Death-Phase
                    lambda rr: jru.render_at(
                        rr, jet_screen_x, jet_screen_y - 2, death_sprite,
                        flip_horizontal=(state.jet_positions[i][2] == -1)
                    ),
                    # Wenn jet lebt
                    lambda rr: jru.render_at(
                        rr, jet_screen_x, jet_screen_y, frame_enemy_jet,
                        flip_horizontal=(state.jet_positions[i][2] == -1)
                    ),
                    raster_base
                )

            return jax.lax.cond(
                should_render,
                render_true,
                lambda r: r,
                raster_base,
            )

        raster = jax.lax.fori_loop(0, self.consts.MAX_JETS, render_enemy_jet, raster)

        # -- CHOPPER Rendering --
        frame_enemy_chopper = jru.get_sprite_frame(SPRITE_ENEMY_HELI, state.step_counter)

        def render_enemy_chopper(i, raster_base):
            death_timer = state.chopper_positions[i][3]

            should_render = jnp.logical_and(state.chopper_positions[i][2] != 0, death_timer > 0)

            chopper_screen_x = state.chopper_positions[i][0] - state.player_x + static_center_x_chopper
            chopper_screen_y = state.chopper_positions[i][1]

            phase0 = death_timer > (2 * self.consts.FRAMES_DEATH_ANIMATION_ENEMY) // 3
            phase1 = jnp.logical_and(
                death_timer <= (2 * self.consts.FRAMES_DEATH_ANIMATION_ENEMY) // 3,
                death_timer > self.consts.FRAMES_DEATH_ANIMATION_ENEMY // 3
            )

            death_sprite = jnp.where(
                phase0, ENEMY_CHOPPER_DEATH_1,
                jnp.where(phase1, ENEMY_CHOPPER_DEATH_2, ENEMY_CHOPPER_DEATH_3)
            )

            return jax.lax.cond(
                should_render,
                lambda r: jru.render_at(
                    r,
                    chopper_screen_x,
                    chopper_screen_y,
                    jnp.where(
                        death_timer <= self.consts.FRAMES_DEATH_ANIMATION_ENEMY,
                        death_sprite,
                        frame_enemy_chopper
                    ),
                    flip_horizontal=(state.chopper_positions[i][2] == -1),
                ),
                lambda r: r,
                raster_base,
            )

        raster = jax.lax.fori_loop(0, self.consts.MAX_CHOPPERS, render_enemy_chopper, raster)

        # Render enemy missiles
        frame_enemy_missile = jru.get_sprite_frame(SPRITE_ENEMY_MISSILE, state.step_counter)

        def render_enemy_missile(i, raster_base):
            should_render = state.enemy_missile_positions[i][1] > 2
            return jax.lax.cond(
                should_render,
                lambda r: jru.render_at(
                    r,
                    state.enemy_missile_positions[i][0] - state.player_x + static_center_x_chopper,
                    state.enemy_missile_positions[i][1],
                    frame_enemy_missile,
                ),
                lambda r: r,
                raster_base,
            )

        raster = jax.lax.fori_loop(0, self.consts.MAX_ENEMY_MISSILES, render_enemy_missile, raster)

        #Render Scores
        def trim_leading_zeros(digits: jnp.ndarray) -> jnp.ndarray:
            is_zero = jnp.all(digits == 0)

            # finde erste Stelle die nicht 0 ist
            first_nonzero = jnp.argmax(digits != 0)

            def on_nonzero():
                # Maske: True ab erster gültiger Ziffer
                mask = jnp.arange(digits.shape[0]) >= first_nonzero
                return jnp.where(mask, digits, -1)

            def on_zero():
                return jnp.array([-1, -1, -1, -1, -1, 0], dtype=digits.dtype)

            return jax.lax.cond(is_zero, on_zero, on_nonzero)

        score_array = jru.int_to_digits(state.score, 6)
        trimmed_digits = trim_leading_zeros(score_array)

        # Nur gültige Digits rendern
        def render_digit(raster, x_offset, digit):
            return jax.lax.cond(
                digit >= 0,
                lambda d: jru.render_label(raster, x_offset, 2, jnp.array([d], dtype=jnp.int32), DIGITS, spacing=8),
                lambda _: raster,
                operand=digit
            )

        # Schrittweise rendern mit X-Verschiebung
        def render_all_digits(raster, digits, spacing=8, x_start=16):
            def body(i, rast):
                return render_digit(rast, x_start + i * spacing, digits[i])

            return jax.lax.fori_loop(0, digits.shape[0], body, raster)

        raster = render_all_digits(raster, trimmed_digits)


        # Render lives
        raster = jru.render_indicator(
            raster, 16, 10, state.lives-1, LIFE_INDICATOR, spacing=9
        )

        # Render Player
        frame_pl_heli = jru.get_sprite_frame(SPRITE_PL_CHOPPER, state.step_counter)

        death_timer = state.pause_timer
        should_render = jnp.logical_and(death_timer != 0, death_timer != 1)

        # Schwellen berechnen
        phase0_cutoff = jnp.array(self.consts.PLAYER_FADE_OUT_START_THRESHOLD_0 * self.consts.DEATH_PAUSE_FRAMES).astype(jnp.int32)
        phase1_cutoff = jnp.array(self.consts.PLAYER_FADE_OUT_START_THRESHOLD_1 * self.consts.DEATH_PAUSE_FRAMES).astype(jnp.int32)

        # Phasen bestimmen
        phase0 = death_timer > phase0_cutoff
        phase1 = jnp.logical_and(
            death_timer <= phase0_cutoff,
            death_timer > phase1_cutoff
        )

        # Entsprechenden Sprite wählen
        death_sprite = jnp.where(
            phase0, PLAYER_DEATH_1,
            jnp.where(phase1, PLAYER_DEATH_2, PLAYER_DEATH_3)
        )

        all_enemies_dead = jnp.logical_and(jnp.all(state.jet_positions == 0), jnp.all(state.chopper_positions == 0))

        # Cond. Rendern
        raster = jax.lax.cond(
            should_render,
            lambda r: jru.render_at(
                r,
                chopper_position,
                state.player_y,
                jnp.where(
                    jnp.logical_or(death_timer > self.consts.DEATH_PAUSE_FRAMES, all_enemies_dead),
                    frame_pl_heli,
                    death_sprite
                ),
                flip_horizontal=(state.player_facing_direction == -1),
            ),
            lambda r: r,
            raster,
        )

        # Render player missiles
        def render_single_missile(i, raster):
            missile = state.player_missile_positions[i]  #Indexierung IN der Funktion
            missile_active = missile[2] != 0


            missile_screen_x = missile[0] - state.player_x + chopper_position
            missile_screen_y = missile[1]

            def get_pl_missile_frame():
                delta_curr_missile_spawn = jnp.abs(missile[0] - missile[4])
                index = jnp.floor_divide(delta_curr_missile_spawn, self.consts.MISSILE_ANIMATION_SPEED)
                index = jnp.clip(index, 0, 15)
                return index.astype(jnp.int32)
            frame_pl_missile = jru.get_sprite_frame(SPRITE_PL_MISSILE, get_pl_missile_frame())


            return jax.lax.cond(
                missile_active,
                lambda r: jru.render_at(
                    r,
                    missile_screen_x,
                    missile_screen_y,
                    frame_pl_missile,
                    flip_horizontal=(missile[2] == -1),
                ),
                lambda r: r,
                raster,
            )

        #Render all missiles (iterate over single missile function)
        raster = jax.lax.fori_loop(
            0,
            state.player_missile_positions.shape[0],
            render_single_missile,
            raster,
        )

        #Render minimap
        raster = self.render_minimap(chopper_position, raster, state)

        return raster

    def render_minimap(self, chopper_position, raster, state):
        # Render minimap background
        raster = jru.render_at(
            raster,
            self.consts.MINIMAP_POSITION_X,
            self.consts.MINIMAP_POSITION_Y,
            MINIMAP_BG,
        )

        # Render minimap mountains
        def get_minimap_mountains_frame():
            return jnp.asarray(((-state.player_x // (self.consts.DOWNSCALING_FACTOR_WIDTH * 7)) % 8), dtype=jnp.int32)

        frame_minimap_mountains = jru.get_sprite_frame(MINIMAP_MOUNTAINS, get_minimap_mountains_frame())
        raster = jru.render_at(
            raster,
            self.consts.MINIMAP_POSITION_X,
            self.consts.MINIMAP_POSITION_Y + 3,
            frame_minimap_mountains,
        )

        # Render trucks on minimap
        def render_trucks_minimap(i, raster_base):
            timing_clock = state.step_counter % self.consts.MINIMAP_RENDER_TRUCK_REFRESH_RATE
            update_trigger = timing_clock == 0

            truck_world_x = state.truck_positions[6][0]

            truck_world_x = jnp.where(update_trigger,
                                      truck_world_x,
                                      truck_world_x + (0.5 * timing_clock)
                                      )

            weird_offset = 16
            parent_x = weird_offset + (
                    (truck_world_x - state.player_x + chopper_position)
                        // self.consts.DOWNSCALING_FACTOR_WIDTH // 6
            )

            minimap_x = 2 * i + parent_x

            is_in_first_fleet = i < 3
            is_in_second_fleet = jnp.logical_and(i >= 3, i <= 5)
            is_in_third_fleet = jnp.logical_and(i >= 6, i <= 8)
            is_in_fourth_fleet = jnp.logical_and(i >= 9, i <= 11)

            add = 11.5
            add_to_first = jnp.where(is_in_first_fleet,
                                     -3 * add,#-1 * add,
                                     0)
            add_to_second = jnp.where(is_in_second_fleet,
                                      -2 * add,
                                      0)

            add_to_third = jnp.where(is_in_third_fleet,
                                     -1 * add,
                                     0)
            add_to_fourth = jnp.where(is_in_fourth_fleet,
                                      0 * add,
                                      0)

            minimap_x = minimap_x + add_to_first + add_to_second + add_to_third + add_to_fourth
            minimap_x = jnp.mod(minimap_x, 6 * add)

            minimap_y = (state.truck_positions[i][1] // self.consts.DOWNSCALING_FACTOR_HEIGHT)

            should_render = jnp.logical_and(
                state.truck_positions[i][3] != 0,
                jnp.logical_and(minimap_x >= 0, minimap_x < self.consts.MINIMAP_WIDTH)
            )

            raster_base = jax.lax.cond(
                should_render,
                lambda r: jru.render_at(
                    r,
                    self.consts.MINIMAP_POSITION_X + minimap_x,
                    self.consts.MINIMAP_POSITION_Y + 1 + minimap_y,
                    MINIMAP_TRUCK
                ),
                lambda r: r,
                raster_base,
            )
            return raster_base

        raster = jax.lax.fori_loop(0, self.consts.MAX_TRUCKS, render_trucks_minimap, raster)


        # Render jets on minimap
        def render_jets_minimap(i, raster_base):
            weird_offset = 16
            jet_world_x = state.jet_positions[i][0]
            minimap_x = weird_offset + (
                        (jet_world_x - state.player_x + chopper_position) // self.consts.DOWNSCALING_FACTOR_WIDTH // 6)

            is_alive = state.jet_positions[i][3] > self.consts.FRAMES_DEATH_ANIMATION_ENEMY

            should_render = jnp.logical_and(
                is_alive,
                jnp.logical_and(
                    minimap_x >= 0,
                    minimap_x < self.consts.MINIMAP_WIDTH
                )
            )

            def do_render(r):
                jet_world_x = state.jet_positions[i][0]
                jet_world_y = state.jet_positions[i][1]

                is_in_top_lane = jnp.logical_and(jet_world_y <= self.consts.ENEMY_LANE_6, jet_world_y >= self.consts.ENEMY_LANE_8)
                is_in_middle_lane = jnp.logical_and(jet_world_y <= self.consts.ENEMY_LANE_3, jet_world_y >= self.consts.ENEMY_LANE_5)

                lane_world_y = jnp.where(is_in_top_lane,
                                         self.consts.ENEMY_LANE_7, jnp.where(is_in_middle_lane,
                                                                 self.consts.ENEMY_LANE_4, self.consts.ENEMY_LANE_1))

                # Downscaling
                minimap_x = weird_offset + (
                            (jet_world_x - state.player_x + chopper_position) // self.consts.DOWNSCALING_FACTOR_WIDTH // 6)
                minimap_y = (lane_world_y // (self.consts.DOWNSCALING_FACTOR_HEIGHT + 1))

                return jru.render_at(
                    r,
                    self.consts.MINIMAP_POSITION_X + minimap_x,
                    self.consts.MINIMAP_POSITION_Y + 3 + minimap_y,
                    MINIMAP_ENEMY
                )

            return jax.lax.cond(should_render, do_render, lambda r: r, raster_base)

        raster = jax.lax.fori_loop(0, self.consts.MAX_JETS, render_jets_minimap, raster)


        # Render choppers on minimap
        def render_choppers_minimap(i, raster_base):
            weird_offset = 16
            chooper_world_x = state.chopper_positions[i][0]
            minimap_x = weird_offset + (
                        (chooper_world_x - state.player_x + chopper_position) // self.consts.DOWNSCALING_FACTOR_WIDTH // 6)

            is_alive = state.chopper_positions[i][3] > self.consts.FRAMES_DEATH_ANIMATION_ENEMY

            should_render = jnp.logical_and(
                is_alive,
                jnp.logical_and(
                    minimap_x >= 0,
                    minimap_x < self.consts.MINIMAP_WIDTH
                )
            )

            def do_render(r):
                chopper_world_x = state.chopper_positions[i][0]
                chopper_world_y = state.chopper_positions[i][1]

                is_in_top_lane = jnp.logical_and(chopper_world_y <= self.consts.ENEMY_LANE_6, chopper_world_y >= self.consts.ENEMY_LANE_8)
                is_in_middle_lane = jnp.logical_and(chopper_world_y <= self.consts.ENEMY_LANE_3, chopper_world_y >= self.consts.ENEMY_LANE_5)

                lane_world_y = jnp.where(is_in_top_lane,
                                         self.consts.ENEMY_LANE_7, jnp.where(is_in_middle_lane,
                                                                 self.consts.ENEMY_LANE_4, self.consts.ENEMY_LANE_1))

                # Downscaling
                minimap_x = weird_offset + (
                            (chopper_world_x - state.player_x + chopper_position) // self.consts.DOWNSCALING_FACTOR_WIDTH // 6)
                minimap_y = (lane_world_y // (self.consts.DOWNSCALING_FACTOR_HEIGHT + 1))

                return jru.render_at(
                    r,
                    self.consts.MINIMAP_POSITION_X + minimap_x,
                    self.consts.MINIMAP_POSITION_Y + 3 + minimap_y,
                    MINIMAP_ENEMY
                )

            return jax.lax.cond(should_render, do_render, lambda r: r, raster_base)

        raster = jax.lax.fori_loop(0, self.consts.MAX_CHOPPERS, render_choppers_minimap, raster)


        # Render player on minimap
        raster = jru.render_at(
            raster,
            self.consts.MINIMAP_POSITION_X + 16 + (chopper_position // (self.consts.DOWNSCALING_FACTOR_WIDTH * 7)),
            self.consts.MINIMAP_POSITION_Y + 6 + (state.player_y // (self.consts.DOWNSCALING_FACTOR_HEIGHT + 7)),
            MINIMAP_PLAYER,
        )

        #Render activision logo
        raster = jru.render_at(
            raster,
            self.consts.MINIMAP_POSITION_X + (self.consts.MINIMAP_WIDTH - 32) // 2,
            self.consts.HEIGHT - 7 - 1, #7 = Sprite Height 1=One pixel headroom
            MINIMAP_ACTIVISION_LOGO,
        )

        return raster

"""
def get_human_action() -> chex.Array:
    Get human action from keyboard with support for diagonal movement and combined fire
    keys = pygame.key.get_pressed()
    up = keys[pygame.K_UP] or keys[pygame.K_w]
    down = keys[pygame.K_DOWN] or keys[pygame.K_s]
    left = keys[pygame.K_LEFT] or keys[pygame.K_a]
    right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
    fire = keys[pygame.K_SPACE]

    # Diagonal movements with fire
    if up and right and fire:
        return jnp.array(Action.UPRIGHTFIRE)
    if up and left and fire:
        return jnp.array(Action.UPLEFTFIRE)
    if down and right and fire:
        return jnp.array(Action.DOWNRIGHTFIRE)
    if down and left and fire:
        return jnp.array(Action.DOWNLEFTFIRE)

    # Cardinal directions with fire
    if up and fire:
        return jnp.array(Action.UPFIRE)
    if down and fire:
        return jnp.array(Action.DOWNFIRE)
    if left and fire:
        return jnp.array(Action.LEFTFIRE)
    if right and fire:
        return jnp.array(Action.RIGHTFIRE)

    # Diagonal movements
    if up and right:
        return jnp.array(Action.UPRIGHT)
    if up and left:
        return jnp.array(Action.UPLEFT)
    if down and right:
        return jnp.array(Action.DOWNRIGHT)
    if down and left:
        return jnp.array(Action.DOWNLEFT)

    # Cardinal directions
    if up:
        return jnp.array(Action.UP)
    if down:
        return jnp.array(Action.DOWN)
    if left:
        return jnp.array(Action.LEFT)
    if right:
        return jnp.array(Action.RIGHT)
    if fire:
        return jnp.array(Action.FIRE)

    return jnp.array(Action.NOOP)

if __name__ == "__main__":
    # Initialize game and renderer
    game = JaxChopperCommand(frameskip=1)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH * SCALING_FACTOR, HEIGHT * SCALING_FACTOR))
    clock = pygame.time.Clock()

    renderer_JAXGame = ChopperCommandRenderer()

    # Get jitted functions
    jitted_step = jax.jit(game.step)
    jitted_reset = jax.jit(game.reset)

    curr_obs, curr_state = jitted_reset()

    # Game loop with rendering
    running = True
    frame_by_frame = False
    frameskip = game.frameskip
    counter = 1

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    frame_by_frame = not frame_by_frame
            elif event.type == pygame.KEYDOWN or (
                event.type == pygame.KEYUP and event.key == pygame.K_n
            ):
                if event.key == pygame.K_n and frame_by_frame:
                    if counter % frameskip == 0:
                        action = get_human_action()
                        curr_obs, curr_state, reward, done, info = jitted_step(
                            curr_state, action
                        )

        if not frame_by_frame:
            if counter % frameskip == 0:
                action = get_human_action()
                curr_obs, curr_state, reward, done, info = jitted_step(
                    curr_state, action
                )

        # render and update pygame
        raster = renderer_JAXGame.render(curr_state)
        jru.update_pygame(screen, raster, SCALING_FACTOR, WIDTH, HEIGHT)
        counter += 1
        clock.tick(60)

    pygame.quit()
"""